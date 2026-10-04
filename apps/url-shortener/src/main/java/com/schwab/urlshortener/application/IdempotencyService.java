package com.schwab.urlshortener.application;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.schwab.urlshortener.api.CreateLinkRequest;
import com.schwab.urlshortener.api.LinkResponse;
import com.schwab.urlshortener.config.ShortUrlProperties;
import com.schwab.urlshortener.domain.Link;
import com.schwab.urlshortener.persistence.IdempotencyRecord;
import com.schwab.urlshortener.persistence.IdempotencyRepository;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Clock;
import java.time.Instant;
import java.util.HexFormat;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class IdempotencyService {
    private static final String ANONYMOUS_SCOPE = "anonymous";
    private final IdempotencyRepository records;
    private final LinkService links;
    private final ShortUrlProperties urls;
    private final ObjectMapper json;
    private final JdbcTemplate jdbc;
    private final Clock clock;

    public IdempotencyService(
            IdempotencyRepository records,
            LinkService links,
            ShortUrlProperties urls,
            ObjectMapper json,
            JdbcTemplate jdbc,
            Clock clock) {
        this.records = records;
        this.links = links;
        this.urls = urls;
        this.json = json;
        this.jdbc = jdbc;
        this.clock = clock;
    }

    @Transactional
    public LinkResponse create(CreateLinkRequest request, String key) {
        if (key == null) {
            return LinkResponse.from(
                    links.create(request.url(), request.customAlias(), request.expiresAt()), urls);
        }
        if (!key.matches("[\\x21-\\x7E]{1,128}")) {
            throw new InvalidIdempotencyKeyException();
        }
        String fingerprint = fingerprint(request);
        // Transaction-scoped lock serializes identical keys across application instances.
        // The unique database constraint remains the final integrity guard.
        jdbc.queryForList(
                "SELECT pg_advisory_xact_lock(hashtextextended(?::text, 0))",
                ANONYMOUS_SCOPE + ":" + key);
        var existing = records.findByCallerScopeAndRequestKey(ANONYMOUS_SCOPE, key);
        if (existing.isPresent()) {
            if (!existing.get().getRequestFingerprint().equals(fingerprint)) {
                throw new LinkConflictException(
                        "IDEMPOTENCY_CONFLICT", "Idempotency-Key was used for a different request");
            }
            try {
                return json.readValue(existing.get().getResponseJson(), LinkResponse.class);
            } catch (JsonProcessingException exception) {
                throw new IllegalStateException(
                        "Stored idempotency response is invalid", exception);
            }
        }
        Link link = links.create(request.url(), request.customAlias(), request.expiresAt());
        LinkResponse response = LinkResponse.from(link, urls);
        try {
            records.saveAndFlush(
                    new IdempotencyRecord(
                            ANONYMOUS_SCOPE,
                            key,
                            fingerprint,
                            link.getId(),
                            json.writeValueAsString(response),
                            Instant.now(clock)));
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Could not store idempotency response", exception);
        }
        return response;
    }

    private String fingerprint(CreateLinkRequest request) {
        try {
            byte[] canonical = json.writeValueAsBytes(request);
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(canonical));
        } catch (JsonProcessingException | NoSuchAlgorithmException exception) {
            throw new IllegalStateException("Could not fingerprint request", exception);
        }
    }
}
