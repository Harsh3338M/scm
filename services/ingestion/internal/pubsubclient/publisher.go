// internal/pubsubclient/publisher.go — Pub/Sub publisher with OTel trace propagation
package pubsubclient

import (
	"context"
	"encoding/json"
	"fmt"

	"cloud.google.com/go/pubsub"
	"github.com/rs/zerolog/log"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
)

// Publisher wraps the Pub/Sub client and topic for publishing messages.
type Publisher struct {
	client *pubsub.Client
	topic  *pubsub.Topic
}

// NewPublisher creates a new Pub/Sub publisher for the given project and topic.
func NewPublisher(ctx context.Context, projectID, topicID string) (*Publisher, error) {
	client, err := pubsub.NewClient(ctx, projectID)
	if err != nil {
		return nil, fmt.Errorf("pubsub.NewClient: %w", err)
	}

	topic := client.Topic(topicID)

	// Verify topic exists
	exists, err := topic.Exists(ctx)
	if err != nil {
		return nil, fmt.Errorf("topic.Exists: %w", err)
	}
	if !exists {
		return nil, fmt.Errorf("pub/sub topic %q does not exist in project %q", topicID, projectID)
	}

	// Configure batching for high throughput
	topic.PublishSettings.DelayThreshold = 100 // 100ms max delay
	topic.PublishSettings.CountThreshold = 100  // batch up to 100 messages
	topic.PublishSettings.ByteThreshold = 1 << 20 // 1MB

	log.Info().Str("project", projectID).Str("topic", topicID).Msg("Pub/Sub publisher initialized")

	return &Publisher{client: client, topic: topic}, nil
}

// Publish sends a message to the Pub/Sub topic, embedding the OTel trace context
// in the message attributes so downstream subscribers can continue the trace.
func (p *Publisher) Publish(ctx context.Context, data []byte, extraAttrs map[string]string) (string, error) {
	// Build attributes map
	attrs := make(map[string]string)
	for k, v := range extraAttrs {
		attrs[k] = v
	}

	// Inject OTel W3C TraceContext into Pub/Sub message attributes
	// This propagates the trace from the HTTP handler through the message broker
	otel.GetTextMapPropagator().Inject(ctx, traceCarrier(attrs))

	msg := &pubsub.Message{
		Data:       data,
		Attributes: attrs,
	}

	result := p.topic.Publish(ctx, msg)

	// Block until the result is confirmed (or failed)
	msgID, err := result.Get(ctx)
	if err != nil {
		return "", fmt.Errorf("topic.Publish result.Get: %w", err)
	}

	return msgID, nil
}

// Stop flushes pending messages and closes the Pub/Sub client.
func (p *Publisher) Stop() {
	p.topic.Stop()
	if err := p.client.Close(); err != nil {
		log.Error().Err(err).Msg("error closing Pub/Sub client")
	}
}

// traceCarrier implements propagation.TextMapCarrier using a string map,
// allowing OTel to inject W3C trace headers into Pub/Sub message attributes.
type traceCarrier map[string]string

func (c traceCarrier) Get(key string) string        { return c[key] }
func (c traceCarrier) Set(key, value string)        { c[key] = value }
func (c traceCarrier) Keys() []string {
	keys := make([]string, 0, len(c))
	for k := range c {
		keys = append(keys, k)
	}
	return keys
}

// ExtractTraceContext extracts OTel trace context from Pub/Sub message attributes.
// Used by downstream subscribers to continue the distributed trace.
func ExtractTraceContext(ctx context.Context, attrs map[string]string) context.Context {
	return otel.GetTextMapPropagator().Extract(ctx, propagation.MapCarrier(attrs))
}

// MarshalToJSON is a helper to serialize any value to JSON bytes.
func MarshalToJSON(v interface{}) ([]byte, error) {
	return json.Marshal(v)
}
