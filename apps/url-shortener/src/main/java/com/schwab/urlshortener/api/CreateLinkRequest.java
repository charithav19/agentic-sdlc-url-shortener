package com.schwab.urlshortener.api;

import jakarta.validation.constraints.NotBlank;
import java.time.Instant;

public record CreateLinkRequest(
        @NotBlank(message = "URL is required") String url, String customAlias, Instant expiresAt) {}
