package com.schwab.urlshortener;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.schwab.urlshortener.config.CreationRateLimitFilter;
import com.schwab.urlshortener.config.RateLimitProperties;
import java.time.Duration;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

class RateLimitTest {
    @Test
    void boundsGlobalWindowAndReturnsRetryAfter() throws Exception {
        MutableClock clock = new MutableClock(Instant.parse("2026-10-04T12:00:00Z"));
        CreationRateLimitFilter filter =
                new CreationRateLimitFilter(
                        new RateLimitProperties(2, Duration.ofSeconds(10)),
                        clock,
                        new ObjectMapper());
        assertThat(post(filter).getStatus()).isEqualTo(200);
        assertThat(post(filter).getStatus()).isEqualTo(200);
        MockHttpServletResponse limited = post(filter);
        assertThat(limited.getStatus()).isEqualTo(429);
        assertThat(limited.getHeader("Retry-After")).isEqualTo("10");
        assertThat(limited.getContentAsString()).contains("RATE_LIMITED");
        clock.set(clock.instant().plusSeconds(10));
        assertThat(post(filter).getStatus()).isEqualTo(200);
    }

    @Test
    void onlyCreateRouteConsumesCapacity() throws Exception {
        CreationRateLimitFilter filter =
                new CreationRateLimitFilter(
                        new RateLimitProperties(1, Duration.ofMinutes(1)),
                        new MutableClock(Instant.parse("2026-10-04T12:00:00Z")),
                        new ObjectMapper());
        MockHttpServletRequest lookup = new MockHttpServletRequest("GET", "/api/v1/links/a");
        lookup.setServletPath("/api/v1/links/a");
        filter.doFilter(lookup, new MockHttpServletResponse(), new MockFilterChain());
        assertThat(post(filter).getStatus()).isEqualTo(200);
        assertThat(post(filter).getStatus()).isEqualTo(429);
    }

    private MockHttpServletResponse post(CreationRateLimitFilter filter) throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/v1/links");
        request.setServletPath("/api/v1/links");
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(request, response, new MockFilterChain());
        return response;
    }
}
