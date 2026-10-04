package com.schwab.urlshortener.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.schwab.urlshortener.api.ApiError;
import com.schwab.urlshortener.observability.TraceIdFilter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 1)
public class CreationRateLimitFilter extends OncePerRequestFilter {
    private final RateLimitProperties properties;
    private final Clock clock;
    private final ObjectMapper json;
    private Instant windowStart;
    private int accepted;

    public CreationRateLimitFilter(RateLimitProperties properties, Clock clock, ObjectMapper json) {
        this.properties = properties;
        this.clock = clock;
        this.json = json;
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String path = request.getRequestURI().substring(request.getContextPath().length());
        if (!"POST".equals(request.getMethod()) || !"/api/v1/links".equals(path)) {
            chain.doFilter(request, response);
            return;
        }
        long retryAfter = acquire();
        if (retryAfter == 0) {
            chain.doFilter(request, response);
            return;
        }
        response.setStatus(429);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setHeader("Retry-After", Long.toString(retryAfter));
        Object trace = request.getAttribute(TraceIdFilter.TRACE_ID_ATTRIBUTE);
        String traceId = trace instanceof String value ? value : UUID.randomUUID().toString();
        response.setHeader("X-Trace-Id", traceId);
        json.writeValue(
                response.getOutputStream(),
                new ApiError(
                        "RATE_LIMITED", "Create-link rate limit exceeded", traceId, List.of()));
    }

    private synchronized long acquire() {
        Instant now = Instant.now(clock);
        if (windowStart == null
                || now.isBefore(windowStart)
                || !now.isBefore(windowStart.plus(properties.window()))) {
            windowStart = now;
            accepted = 0;
        }
        if (accepted < properties.capacity()) {
            accepted++;
            return 0;
        }
        Duration left = Duration.between(now, windowStart.plus(properties.window()));
        return Math.max(1, (left.toMillis() + 999) / 1000);
    }
}
