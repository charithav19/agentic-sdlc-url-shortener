package com.schwab.urlshortener.api;

import java.util.List;

public record ApiError(String code, String message, String traceId, List<Detail> details) {
    public record Detail(String field, String message) {}
}
