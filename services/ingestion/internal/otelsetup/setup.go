// internal/otelsetup/setup.go — OpenTelemetry SDK initialization
package otelsetup

import (
	"context"
	"fmt"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// InitTracer configures and registers a global OpenTelemetry TracerProvider
// that exports spans via OTLP gRPC to the given endpoint (e.g., Cloud Trace collector).
// Returns a shutdown function to be deferred by the caller.
func InitTracer(ctx context.Context, otlpEndpoint, serviceName, serviceVersion string) (func(context.Context) error, error) {
	// ── gRPC connection to OTLP collector ─────────────────────────────
	conn, err := grpc.NewClient(
		otlpEndpoint,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create gRPC connection to OTLP endpoint %q: %w", otlpEndpoint, err)
	}

	// ── OTLP trace exporter ────────────────────────────────────────────
	exporter, err := otlptracegrpc.New(ctx,
		otlptracegrpc.WithGRPCConn(conn),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create OTLP trace exporter: %w", err)
	}

	// ── Resource metadata (service identity) ──────────────────────────
	res, err := resource.New(ctx,
		resource.WithAttributes(
			semconv.ServiceNameKey.String(serviceName),
			semconv.ServiceVersionKey.String(serviceVersion),
			attribute.String("deployment.environment", "production"),
			attribute.String("cloud.provider", "gcp"),
			attribute.String("cloud.platform", "gcp_cloud_run"),
		),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create OTel resource: %w", err)
	}

	// ── TracerProvider ─────────────────────────────────────────────────
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter,
			sdktrace.WithBatchTimeout(5*time.Second),
			sdktrace.WithMaxExportBatchSize(512),
		),
		sdktrace.WithResource(res),
		// Sample 100% in dev; in prod, use ParentBased(TraceIDRatioBased(0.1))
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)

	// Register as the global provider
	otel.SetTracerProvider(tp)

	return tp.Shutdown, nil
}
