package com.schwab.urlshortener;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.schwab.urlshortener.application.CollisionRetryExecutor;
import com.schwab.urlshortener.application.InvalidExpiryException;
import com.schwab.urlshortener.application.LinkNotFoundException;
import com.schwab.urlshortener.application.LinkService;
import com.schwab.urlshortener.domain.AliasValidator;
import com.schwab.urlshortener.domain.InvalidUrlException;
import com.schwab.urlshortener.domain.Link;
import com.schwab.urlshortener.domain.UrlValidator;
import com.schwab.urlshortener.persistence.LinkRepository;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

class LinkServiceTest {
    private final LinkRepository repository = org.mockito.Mockito.mock(LinkRepository.class);
    private final CollisionRetryExecutor retry =
            org.mockito.Mockito.mock(CollisionRetryExecutor.class);
    private final JdbcTemplate jdbc = org.mockito.Mockito.mock(JdbcTemplate.class);
    private final Instant now = Instant.parse("2026-10-04T12:00:00Z");
    private final Clock clock = Clock.fixed(now, ZoneOffset.UTC);
    private final LinkService service =
            new LinkService(
                    repository, retry, new UrlValidator(), new AliasValidator(), clock, jdbc);

    @Test
    void createsWithValidatedArgumentsAndClock() {
        Link expected = new Link("chosen_alias", "https://example.com/a", now, now.plusSeconds(60));
        when(retry.create(eq("https://example.com/a"), eq("chosen_alias"), eq(now), any()))
                .thenReturn(expected);
        Link actual = service.create("https://example.com/a", "chosen_alias", now.plusSeconds(60));
        assertThat(actual).isSameAs(expected);
    }

    @Test
    void invalidUrlAndExpiryNeverReachDatabase() {
        assertThatThrownBy(() -> service.create("javascript:alert(1)"))
                .isInstanceOf(InvalidUrlException.class);
        assertThatThrownBy(() -> service.create("https://example.com", null, now))
                .isInstanceOf(InvalidExpiryException.class);
        verify(retry, never()).create(any(), any(), any(), any());
    }

    @Test
    void missingCodeIsExplicit() {
        when(repository.findByShortCode("missing")).thenReturn(Optional.empty());
        assertThatThrownBy(() -> service.findByCode("missing"))
                .isInstanceOf(LinkNotFoundException.class);
    }
}
