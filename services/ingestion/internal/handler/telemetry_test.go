// internal/handler/telemetry_test.go — Unit tests for DPI handler
package handler_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"golang/internal/handler"
)

// mockPublisher satisfies the publisher interface for testing without a real Pub/Sub connection.
type mockPublisher struct {
	published [][]byte
	shouldErr bool
}

func (m *mockPublisher) Publish(ctx interface{}, data []byte, attrs map[string]string) (string, error) {
	if m.shouldErr {
		return "", assert.AnError
	}
	m.published = append(m.published, data)
	return "mock-msg-id-123", nil
}

func validPayload(t *testing.T) []byte {
	t.Helper()
	temp := 22.5
	hum := 60.0
	spd := 80.0
	bat := 85.0
	payload := handler.TelemetryPayload{
		DeviceID:   "device-001",
		ShipmentID: "ship-abc-123",
		Timestamp:  time.Now().UTC(),
		Lat:        28.6139,
		Lon:        77.2090,
		Temperature: &temp,
		Humidity:    &hum,
		SpeedKmh:    &spd,
		BatteryPct:  &bat,
	}
	b, err := json.Marshal(payload)
	require.NoError(t, err)
	return b
}

func TestHandleTelemetry_ValidPayload(t *testing.T) {
	// Arrange
	pub := &mockPublisher{}
	h := handler.NewTelemetryHandler(pub)

	req := httptest.NewRequest(http.MethodPost, "/ingest/telemetry", bytes.NewReader(validPayload(t)))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	// Act
	h.HandleTelemetry(w, req)

	// Assert
	assert.Equal(t, http.StatusAccepted, w.Code)
	assert.Len(t, pub.published, 1)

	var resp map[string]string
	require.NoError(t, json.Unmarshal(w.Body.Bytes(), &resp))
	assert.Equal(t, "accepted", resp["status"])
	assert.Equal(t, "mock-msg-id-123", resp["message_id"])
}

func TestHandleTelemetry_MissingDeviceID(t *testing.T) {
	pub := &mockPublisher{}
	h := handler.NewTelemetryHandler(pub)

	payload := map[string]interface{}{
		"shipment_id": "ship-abc",
		"timestamp":   time.Now().UTC(),
		"lat":         28.6,
		"lon":         77.2,
	}
	b, _ := json.Marshal(payload)

	req := httptest.NewRequest(http.MethodPost, "/ingest/telemetry", bytes.NewReader(b))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	h.HandleTelemetry(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
	assert.Empty(t, pub.published)
}

func TestHandleTelemetry_InvalidLatitude(t *testing.T) {
	pub := &mockPublisher{}
	h := handler.NewTelemetryHandler(pub)

	payload := map[string]interface{}{
		"device_id":   "device-001",
		"shipment_id": "ship-abc",
		"timestamp":   time.Now().UTC(),
		"lat":         999.0, // INVALID
		"lon":         77.2,
	}
	b, _ := json.Marshal(payload)

	req := httptest.NewRequest(http.MethodPost, "/ingest/telemetry", bytes.NewReader(b))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	h.HandleTelemetry(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestHandleTelemetry_StaleTimestamp(t *testing.T) {
	pub := &mockPublisher{}
	h := handler.NewTelemetryHandler(pub)

	staleTime := time.Now().Add(-48 * time.Hour) // 48 hours old
	payload := map[string]interface{}{
		"device_id":   "device-001",
		"shipment_id": "ship-abc",
		"timestamp":   staleTime,
		"lat":         28.6,
		"lon":         77.2,
	}
	b, _ := json.Marshal(payload)

	req := httptest.NewRequest(http.MethodPost, "/ingest/telemetry", bytes.NewReader(b))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	h.HandleTelemetry(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestHandleTelemetry_WrongContentType(t *testing.T) {
	pub := &mockPublisher{}
	h := handler.NewTelemetryHandler(pub)

	req := httptest.NewRequest(http.MethodPost, "/ingest/telemetry", bytes.NewReader(validPayload(t)))
	req.Header.Set("Content-Type", "text/plain") // Wrong
	w := httptest.NewRecorder()

	h.HandleTelemetry(w, req)

	assert.Equal(t, http.StatusUnsupportedMediaType, w.Code)
}

func TestHandleTelemetry_PublisherError(t *testing.T) {
	pub := &mockPublisher{shouldErr: true}
	h := handler.NewTelemetryHandler(pub)

	req := httptest.NewRequest(http.MethodPost, "/ingest/telemetry", bytes.NewReader(validPayload(t)))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	h.HandleTelemetry(w, req)

	assert.Equal(t, http.StatusInternalServerError, w.Code)
}
