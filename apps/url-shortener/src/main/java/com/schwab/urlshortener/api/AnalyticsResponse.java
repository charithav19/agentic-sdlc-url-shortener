package com.schwab.urlshortener.api;

import java.util.Map;

public record AnalyticsResponse(
        String shortCode, long totalClicks, Map<String, Long> clicksByDay) {}
