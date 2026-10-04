package com.schwab.urlshortener.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "shortener.analytics")
public record AnalyticsProperties(boolean enabled, int maxThreads, int queueCapacity) {
    public AnalyticsProperties {
        if (maxThreads < 1 || maxThreads > 8 || queueCapacity < 1 || queueCapacity > 10000) {
            throw new IllegalArgumentException(
                    "Analytics threads and queue capacity must be bounded and positive");
        }
    }
}
