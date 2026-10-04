package com.schwab.urlshortener.application;

import com.schwab.urlshortener.domain.Link;
import com.schwab.urlshortener.domain.ShortCodeGenerator;
import com.schwab.urlshortener.persistence.LinkRepository;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
public class CollisionRetryExecutor {
    private static final int MAX_ATTEMPTS = 5;
    private final JdbcTemplate jdbc;
    private final LinkRepository links;
    private final ShortCodeGenerator generator;

    public CollisionRetryExecutor(
            JdbcTemplate jdbc, LinkRepository links, ShortCodeGenerator generator) {
        this.jdbc = jdbc;
        this.links = links;
        this.generator = generator;
    }

    public Link create(String url, String alias, Instant createdAt, Instant expiresAt) {
        int attempts = alias == null ? MAX_ATTEMPTS : 1;
        for (int attempt = 0; attempt < attempts; attempt++) {
            String code = alias == null ? generator.generate() : alias;
            int inserted =
                    jdbc.update(
                            """
                            INSERT INTO links (id, short_code, original_url, status, created_at, expires_at, version)
                            VALUES (?, ?, ?, 'ACTIVE', ?, ?, 0)
                            ON CONFLICT (short_code) DO NOTHING
                            """,
                            UUID.randomUUID(),
                            code,
                            url,
                            Timestamp.from(createdAt),
                            expiresAt == null ? null : Timestamp.from(expiresAt));
            if (inserted == 1) {
                return links.findByShortCode(code).orElseThrow();
            }
            if (alias != null) {
                throw new LinkConflictException("ALIAS_CONFLICT", "Alias is already in use");
            }
        }
        throw new CollisionExhaustedException();
    }
}
