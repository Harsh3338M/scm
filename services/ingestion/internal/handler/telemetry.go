// internal/handler/telemetry.go — Deep Packet Inspection & validation
package handler

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/rs/zerolog/log"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"

	"golang/internal/pubsubclient"
)

var tracer = otel.Tracer("nexgen-ingestion/handler")

// TelemetryPayload defines the expected IoT/GPS telemetry structure.
// Any inbound message that does not conform is rejected (DPI).
type TelemetryPayload struct {
	DeviceID    string    `json:"device_id"`
	Timestamp   time.Time `json:"timestamp"`
	Lat         float64   `json:"lat"`
	Lon         float64   `json:"lon"`
	Temperature *float64  `json:"temperature,omitempty"`
	Humidity    *float64  `json:"humidity,omitempty"`
	SpeedKmh    *float64  `json:"speed_kmh,omitempty"`
	BatteryPct  *float64  `json:"battery_pct,omitempty"`
	ShipmentID  string    `json:"shipment_id"`
}

// validate enforces deep packet inspection rules on the telemetry payload.
func (p *TelemetryPayload) validate() error {
	if p.DeviceID == "" {
		return fmt.Errorf("missing required field: device_id")
	}
	if p.ShipmentID == "" {
		return fmt.Errorf("missing required field: shipment_id")
	}
	if p.Timestamp.IsZero() {
		return fmt.Errorf("missing required field: timestamp")
	}
	// Reject suspiciously old messages (> 24h) — replay attack prevention
	if time.Since(p.Timestamp) > 24*time.Hour {
		return fmt.Errorf("stale timestamp — possible replay attack (device_id=%s)", p.DeviceID)
	}
	// Validate GPS bounds
	if p.Lat < -90 || p.Lat > 90 {
		return fmt.Errorf("invalid latitude: %f (must be -90..90)", p.Lat)
	}
	if p.Lon < -180 || p.Lon > 180 {
		return fmt.Errorf("invalid longitude: %f (must be -180..180)", p.Lon)
	}
	// Validate optional sensor ranges
	if p.Temperature != nil && (*p.Temperature < -100 || *p.Temperature > 200) {
		return fmt.Errorf("temperature out of physical range: %f", *p.Temperature)
	}
	if p.Humidity != nil && (*p.Humidity < 0 || *p.Humidity > 100) {
		return fmt.Errorf("humidity out of range: %f", *p.Humidity)
	}
	if p.BatteryPct != nil && (*p.BatteryPct < 0 || *p.BatteryPct > 100) {
		return fmt.Errorf("battery_pct out of range: %f", *p.BatteryPct)
	}
	return nil
}

// TelemetryHandler handles POST /ingest/telemetry
type TelemetryHandler struct {
	publisher *pubsubclient.Publisher
}

// NewTelemetryHandler creates a new TelemetryHandler with the given publisher.
func NewTelemetryHandler(publisher *pubsubclient.Publisher) *TelemetryHandler {
	return &TelemetryHandler{publisher: publisher}
}

// HandleTelemetry is the HTTP handler for telemetry ingestion.
func (h *TelemetryHandler) HandleTelemetry(w http.ResponseWriter, r *http.Request) {
	ctx, span := tracer.Start(r.Context(), "HandleTelemetry")
	defer span.End()

	// ── 1. Read body (limit to 1MB to prevent DoS) ────────────────────
	body, err := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	if err != nil {
		span.SetStatus(codes.Error, "failed to read body")
		writeError(w, http.StatusBadRequest, "failed to read request body")
		return
	}
	defer r.Body.Close()

	// ── 2. Content-Type enforcement ───────────────────────────────────
	ct := r.Header.Get("Content-Type")
	if ct != "application/json" {
		span.SetStatus(codes.Error, "invalid content-type")
		writeError(w, http.StatusUnsupportedMediaType, "Content-Type must be application/json")
		return
	}

	// ── 3. JSON deserialization ───────────────────────────────────────
	var payload TelemetryPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		span.SetStatus(codes.Error, "json parse error")
		log.Warn().Err(err).Str("body_snippet", truncate(string(body), 200)).Msg("DPI: malformed JSON")
		writeError(w, http.StatusBadRequest, fmt.Sprintf("invalid JSON: %v", err))
		return
	}

	// ── 4. Deep Packet Inspection (business rule validation) ──────────
	if err := payload.validate(); err != nil {
		span.SetStatus(codes.Error, "DPI validation failed")
		span.SetAttributes(attribute.String("dpi.rejection_reason", err.Error()))
		log.Warn().Err(err).Str("device_id", payload.DeviceID).Msg("DPI: payload rejected")
		writeError(w, http.StatusBadRequest, fmt.Sprintf("payload validation failed: %v", err))
		return
	}

	span.SetAttributes(
		attribute.String("device.id", payload.DeviceID),
		attribute.String("shipment.id", payload.ShipmentID),
		attribute.Float64("gps.lat", payload.Lat),
		attribute.Float64("gps.lon", payload.Lon),
	)

	// ── 5. Re-serialize and publish to Pub/Sub ────────────────────────
	msgBytes, _ := json.Marshal(payload)
	msgID, err := h.publisher.Publish(ctx, msgBytes, map[string]string{
		"device_id":   payload.DeviceID,
		"shipment_id": payload.ShipmentID,
		"content_type": "application/json",
	})
	if err != nil {
		span.SetStatus(codes.Error, "pubsub publish failed")
		log.Error().Err(err).Str("device_id", payload.DeviceID).Msg("failed to publish to Pub/Sub")
		writeError(w, http.StatusInternalServerError, "failed to enqueue telemetry")
		return
	}

	log.Info().
		Str("device_id", payload.DeviceID).
		Str("shipment_id", payload.ShipmentID).
		Str("msg_id", msgID).
		Msg("telemetry accepted and published")

	span.SetAttributes(attribute.String("pubsub.message_id", msgID))
	span.SetStatus(codes.Ok, "published")

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted)
	_ = json.NewEncoder(w).Encode(map[string]string{
		"status":     "accepted",
		"message_id": msgID,
		"device_id":  payload.DeviceID,
	})
}

func writeError(w http.ResponseWriter, status int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]string{"error": msg})
}

func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}
