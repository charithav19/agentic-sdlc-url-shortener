package com.schwab.urlshortener.api;

import com.schwab.urlshortener.config.ShortUrlProperties;
import com.schwab.urlshortener.domain.Link;
import com.schwab.urlshortener.domain.LinkStatus;
import java.time.Instant;
import java.util.UUID;

public record LinkResponse(
        UUID id,
        String shortCode,
        String shortUrl,
        String url,
        LinkStatus status,
        Instant createdAt,
        Instant expiresAt) {
    public static LinkResponse from(Link link, ShortUrlProperties urls) {
        return new LinkResponse(
                link.getId(),
                link.getShortCode(),
                urls.shortUrl(link.getShortCode()),
                link.getUrl(),
                link.getStatus(),
                link.getCreatedAt(),
                link.getExpiresAt());
    }
}
