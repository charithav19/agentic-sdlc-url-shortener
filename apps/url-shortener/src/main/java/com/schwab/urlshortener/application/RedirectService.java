package com.schwab.urlshortener.application;

import com.schwab.urlshortener.analytics.AnalyticsRecorder;
import com.schwab.urlshortener.domain.Link;
import com.schwab.urlshortener.domain.LinkStatus;
import com.schwab.urlshortener.observability.UrlMetrics;
import jakarta.servlet.http.HttpServletRequest;
import java.time.Clock;
import java.time.Instant;
import org.springframework.stereotype.Service;

@Service
public class RedirectService {
    private final LinkService linkService;
    private final Clock clock;
    private final AnalyticsRecorder analytics;
    private final UrlMetrics metrics;

    public RedirectService(
            LinkService linkService, Clock clock, AnalyticsRecorder analytics, UrlMetrics metrics) {
        this.linkService = linkService;
        this.clock = clock;
        this.analytics = analytics;
        this.metrics = metrics;
    }

    public String destinationFor(String shortCode, HttpServletRequest request) {
        Link link = linkService.findByCode(shortCode);
        if (link.getStatus() != LinkStatus.ACTIVE
                || (link.getExpiresAt() != null
                        && !Instant.now(clock).isBefore(link.getExpiresAt()))) {
            throw new LinkGoneException();
        }
        metrics.redirectSucceeded();
        try {
            analytics.record(link, request);
        } catch (RuntimeException exception) {
            metrics.analyticsFailed();
        }
        return link.getUrl();
    }
}
