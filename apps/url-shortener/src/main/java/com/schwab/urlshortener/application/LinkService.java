package com.schwab.urlshortener.application;

import com.schwab.urlshortener.domain.AliasValidator;
import com.schwab.urlshortener.domain.Link;
import com.schwab.urlshortener.domain.UrlValidator;
import com.schwab.urlshortener.persistence.LinkRepository;
import java.time.Clock;
import java.time.Instant;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class LinkService {
    private final LinkRepository repository;
    private final CollisionRetryExecutor collisionRetry;
    private final UrlValidator urlValidator;
    private final AliasValidator aliasValidator;
    private final Clock clock;
    private final JdbcTemplate jdbc;

    public LinkService(
            LinkRepository repository,
            CollisionRetryExecutor collisionRetry,
            UrlValidator urlValidator,
            AliasValidator aliasValidator,
            Clock clock,
            JdbcTemplate jdbc) {
        this.repository = repository;
        this.collisionRetry = collisionRetry;
        this.urlValidator = urlValidator;
        this.aliasValidator = aliasValidator;
        this.clock = clock;
        this.jdbc = jdbc;
    }

    @Transactional
    public Link create(String url) {
        return create(url, null, null);
    }

    @Transactional
    public Link create(String url, String alias, Instant expiresAt) {
        String validUrl = urlValidator.validate(url);
        String validAlias = aliasValidator.validate(alias);
        Instant now = Instant.now(clock);
        if (expiresAt != null && !expiresAt.isAfter(now)) {
            throw new InvalidExpiryException();
        }
        return collisionRetry.create(validUrl, validAlias, now, expiresAt);
    }

    @Transactional(readOnly = true)
    public Link findByCode(String shortCode) {
        return repository.findByShortCode(shortCode).orElseThrow(LinkNotFoundException::new);
    }

    @Transactional
    public void disable(String shortCode) {
        int changed =
                jdbc.update(
                        "UPDATE links SET status = 'DISABLED', version = version + 1 WHERE short_code = ? AND status = 'ACTIVE'",
                        shortCode);
        if (changed == 0 && repository.findByShortCode(shortCode).isEmpty()) {
            throw new LinkNotFoundException();
        }
    }
}
