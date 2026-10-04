package com.schwab.urlshortener;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;

import com.schwab.urlshortener.analytics.AnalyticsRecorder;
import com.schwab.urlshortener.analytics.AnalyticsWriter;
import com.schwab.urlshortener.config.AnalyticsProperties;
import com.schwab.urlshortener.domain.Link;
import com.schwab.urlshortener.observability.UrlMetrics;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.concurrent.RejectedExecutionException;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

class AnalyticsRecorderTest {
    @Test
    void fullQueueDropsOnlyAnalyticsAndIncrementsCounter() {
        ThreadPoolTaskExecutor executor = mock(ThreadPoolTaskExecutor.class);
        doThrow(new RejectedExecutionException("full queue"))
                .when(executor)
                .execute(any(Runnable.class));
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        AnalyticsRecorder recorder =
                new AnalyticsRecorder(
                        mock(AnalyticsWriter.class),
                        executor,
                        new AnalyticsProperties(true, 1, 1),
                        new UrlMetrics(registry),
                        Clock.fixed(Instant.parse("2026-10-04T12:00:00Z"), ZoneOffset.UTC));

        recorder.record(
                new Link("Abc0123", "https://example.com", Instant.parse("2026-10-04T12:00:00Z")),
                new MockHttpServletRequest());

        assertThat(registry.get("url.analytics.dropped").counter().count()).isEqualTo(1);
    }
}
