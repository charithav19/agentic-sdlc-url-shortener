package com.schwab.urlshortener.api;

import com.schwab.urlshortener.analytics.AnalyticsService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class AnalyticsController {
    private final AnalyticsService analytics;

    public AnalyticsController(AnalyticsService analytics) {
        this.analytics = analytics;
    }

    @GetMapping("/api/v1/links/{shortCode}/analytics")
    public AnalyticsResponse analytics(@PathVariable String shortCode) {
        return analytics.forCode(shortCode);
    }
}
