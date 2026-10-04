package com.schwab.urlshortener.analytics;

import com.schwab.urlshortener.config.AnalyticsProperties;
import com.schwab.urlshortener.domain.Link;
import com.schwab.urlshortener.observability.TraceIdFilter;
import com.schwab.urlshortener.observability.UrlMetrics;
import jakarta.servlet.http.HttpServletRequest;
import java.net.URI;
import java.time.Clock;
import java.time.Instant;
import java.util.Locale;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.stereotype.Component;

@Component
public class AnalyticsRecorder {
    private static final Logger log = LoggerFactory.getLogger(AnalyticsRecorder.class);
    private final AnalyticsWriter writer;
    private final ThreadPoolTaskExecutor executor;
    private final AnalyticsProperties properties;
    private final UrlMetrics metrics;
    private final Clock clock;

    public AnalyticsRecorder(
            AnalyticsWriter writer,
            @Qualifier("analyticsExecutor") ThreadPoolTaskExecutor executor,
            AnalyticsProperties properties,
            UrlMetrics metrics,
            Clock clock) {
        this.writer = writer;
        this.executor = executor;
        this.properties = properties;
        this.metrics = metrics;
        this.clock = clock;
    }

    public void record(Link link, HttpServletRequest request) {
        if (!properties.enabled()) {
            return;
        }
        Object trace = request.getAttribute(TraceIdFilter.TRACE_ID_ATTRIBUTE);
        String traceId = trace instanceof String value ? value : UUID.randomUUID().toString();
        ClickEvent event =
                new ClickEvent(
                        link.getId(),
                        Instant.now(clock),
                        sanitizeReferrer(request.getHeader("Referer")),
                        categorizeUserAgent(request.getHeader("User-Agent")),
                        traceId);
        try {
            executor.execute(
                    () -> {
                        try {
                            writer.persist(event);
                            metrics.analyticsRecorded();
                        } catch (RuntimeException exception) {
                            metrics.analyticsFailed();
                            log.warn(
                                    "event=analytics_write_failed traceId={} errorType={}",
                                    traceId,
                                    exception.getClass().getSimpleName());
                        }
                    });
        } catch (RuntimeException exception) {
            metrics.analyticsDropped();
            log.warn("event=analytics_queue_rejected traceId={}", traceId);
        }
    }

    static String sanitizeReferrer(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            URI referrer = URI.create(value);
            String scheme = referrer.getScheme();
            String host = referrer.getHost();
            if (scheme == null
                    || host == null
                    || referrer.getRawUserInfo() != null
                    || !(scheme.equalsIgnoreCase("http") || scheme.equalsIgnoreCase("https"))) {
                return null;
            }
            String origin =
                    scheme.toLowerCase(Locale.ROOT)
                            + "://"
                            + host.toLowerCase(Locale.ROOT)
                            + (referrer.getPort() < 0 ? "" : ":" + referrer.getPort());
            return origin.length() <= 512 ? origin : null;
        } catch (IllegalArgumentException exception) {
            return null;
        }
    }

    static String categorizeUserAgent(String value) {
        if (value == null) {
            return "OTHER";
        }
        String agent = value.toLowerCase(Locale.ROOT);
        if (agent.contains("bot") || agent.contains("crawler") || agent.contains("spider")) {
            return "BOT";
        }
        if (agent.contains("mobile") || agent.contains("iphone") || agent.contains("android")) {
            return "MOBILE";
        }
        if (agent.contains("windows") || agent.contains("macintosh") || agent.contains("linux")) {
            return "DESKTOP";
        }
        return "OTHER";
    }
}
