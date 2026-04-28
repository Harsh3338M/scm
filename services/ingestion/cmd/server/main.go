// cmd/server/main.go — NexGen SCM Ingestion Service entrypoint
package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"

	"golang/internal/handler"
	"golang/internal/otelsetup"
	"golang/internal/pubsubclient"
)

func main() {
	// ── Logger ──────────────────────────────────────────────────────────
	zerolog.TimeFieldFormat = zerolog.TimeFormatUnix
	if os.Getenv("LOG_FORMAT") == "pretty" {
		log.Logger = log.Output(zerolog.ConsoleWriter{Out: os.Stderr})
	}

	// ── Config ───────────────────────────────────────────────────────────
	projectID := getEnv("GCP_PROJECT_ID", "nexgen-scm-2026")
	topicID := getEnv("PUBSUB_TOPIC_ID", "telemetry-raw")
	port := getEnv("PORT", "8080")
	otlpEndpoint := getEnv("OTLP_ENDPOINT", "localhost:4317")

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// ── OpenTelemetry ────────────────────────────────────────────────────
	shutdown, err := otelsetup.InitTracer(ctx, otlpEndpoint, "nexgen-ingestion", "1.0.0")
	if err != nil {
		log.Fatal().Err(err).Msg("failed to initialize OpenTelemetry tracer")
	}
	defer func() {
		shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer shutdownCancel()
		if err := shutdown(shutdownCtx); err != nil {
			log.Error().Err(err).Msg("error shutting down tracer")
		}
	}()

	// Set global propagator for trace context injection
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	// ── Pub/Sub Publisher ─────────────────────────────────────────────────
	publisher, err := pubsubclient.NewPublisher(ctx, projectID, topicID)
	if err != nil {
		log.Fatal().Err(err).Msg("failed to create Pub/Sub publisher")
	}
	defer publisher.Stop()

	// ── HTTP Router ───────────────────────────────────────────────────────
	r := chi.NewRouter()

	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Use(middleware.Recoverer)
	r.Use(middleware.Timeout(30 * time.Second))
	r.Use(otelMiddleware)

	// Health probe — must always return 200 quickly
	r.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok","service":"nexgen-ingestion"}`))
	})

	// Readiness probe
	r.Get("/ready", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ready"}`))
	})

	// Telemetry ingestion endpoint
	telemetryHandler := handler.NewTelemetryHandler(publisher)
	r.Post("/ingest/telemetry", telemetryHandler.HandleTelemetry)

	// ── HTTP Server ────────────────────────────────────────────────────────
	srv := &http.Server{
		Addr:         fmt.Sprintf(":%s", port),
		Handler:      r,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Graceful shutdown on SIGTERM / SIGINT
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		log.Info().Str("port", port).Str("project", projectID).Str("topic", topicID).
			Msg("🚀 NexGen Ingestion Service starting")
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatal().Err(err).Msg("server error")
		}
	}()

	<-quit
	log.Info().Msg("Shutdown signal received — draining connections...")

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Error().Err(err).Msg("forced shutdown")
	}
	log.Info().Msg("Server stopped gracefully")
}

// otelMiddleware injects OpenTelemetry span context into each HTTP request
func otelMiddleware(next http.Handler) http.Handler {
	tracer := otel.Tracer("nexgen-ingestion/http")
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		propagator := otel.GetTextMapPropagator()
		ctx := propagator.Extract(r.Context(), propagation.HeaderCarrier(r.Header))
		ctx, span := tracer.Start(ctx, fmt.Sprintf("%s %s", r.Method, r.URL.Path))
		defer span.End()
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func getEnv(key, defaultVal string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultVal
}
