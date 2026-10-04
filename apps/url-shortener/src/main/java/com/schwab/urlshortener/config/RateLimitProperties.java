package com.schwab.urlshortener.config;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "shortener.rate-limit")
public record RateLimitProperties(int capacity, Duration window) {
    public RateLimitProperties {
        if (capacity < 1 || window == null || window.isZero() || window.isNegative()) {
            throw new IllegalArgumentException("Rate limit capacity and window must be positive");
        }
    }
}
