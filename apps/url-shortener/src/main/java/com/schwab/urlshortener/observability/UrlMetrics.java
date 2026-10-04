package com.schwab.urlshortener.observability;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

@Component
public class UrlMetrics {
    private final Counter redirects;
    private final Counter analyticsRecorded;
    private final Counter analyticsFailures;
    private final Counter analyticsDropped;

    public UrlMetrics(MeterRegistry registry) {
        redirects =
                Counter.builder("url.redirect.success")
                        .description("Valid redirects")
                        .register(registry);
        analyticsRecorded =
                Counter.builder("url.analytics.recorded")
                        .description("Persisted click events")
                        .register(registry);
        analyticsFailures =
                Counter.builder("url.analytics.failure")
                        .description("Click event persistence failures")
                        .register(registry);
        analyticsDropped =
                Counter.builder("url.analytics.dropped")
                        .description("Click events rejected before persistence")
                        .register(registry);
    }

    public void redirectSucceeded() {
        redirects.increment();
    }

    public void analyticsRecorded() {
        analyticsRecorded.increment();
    }

    public void analyticsFailed() {
        analyticsFailures.increment();
    }

    public void analyticsDropped() {
        analyticsDropped.increment();
    }
}
