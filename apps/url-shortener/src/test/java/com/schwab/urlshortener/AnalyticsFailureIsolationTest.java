package com.schwab.urlshortener;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.schwab.urlshortener.analytics.AnalyticsWriter;
import com.schwab.urlshortener.application.LinkService;
import io.micrometer.core.instrument.MeterRegistry;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class AnalyticsFailureIsolationTest extends UrlIntegrationTestSupport {
    @Autowired MockMvc client;
    @Autowired LinkService linksService;
    @Autowired MeterRegistry registry;
    @MockitoBean AnalyticsWriter writer;

    @Test
    void persistenceExceptionDoesNotPrevent302AndIsCounted() throws Exception {
        String code =
                linksService
                        .create("https://example.com/valid", "write_fails", null)
                        .getShortCode();
        double before = failureCount();
        CountDownLatch called = new CountDownLatch(1);
        doAnswer(
                        invocation -> {
                            called.countDown();
                            throw new IllegalStateException("forced analytics write failure");
                        })
                .when(writer)
                .persist(any());

        client.perform(get("/{code}", code))
                .andExpect(status().isFound())
                .andExpect(header().string("Location", "https://example.com/valid"));
        assertThat(called.await(5, TimeUnit.SECONDS)).isTrue();
        awaitFailureCount(before + 1);
    }

    @Test
    void stalledAnalyticsWriteDoesNotDelayRedirect() throws Exception {
        String code =
                linksService.create("https://example.com/valid", "slow_write", null).getShortCode();
        double before = failureCount();
        CountDownLatch entered = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        doAnswer(
                        invocation -> {
                            entered.countDown();
                            if (!release.await(5, TimeUnit.SECONDS)) {
                                throw new IllegalStateException("forced analytics timeout");
                            }
                            throw new IllegalStateException("forced analytics timeout");
                        })
                .when(writer)
                .persist(any());

        try {
            client.perform(get("/{code}", code))
                    .andExpect(status().isFound())
                    .andExpect(header().string("Location", "https://example.com/valid"));
            assertThat(entered.await(5, TimeUnit.SECONDS)).isTrue();
        } finally {
            release.countDown();
        }
        awaitFailureCount(before + 1);
    }

    private double failureCount() {
        return registry.get("url.analytics.failure").counter().count();
    }

    private void awaitFailureCount(double expected) throws InterruptedException {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
        while (failureCount() < expected && System.nanoTime() < deadline) {
            Thread.sleep(20);
        }
        assertThat(failureCount()).isGreaterThanOrEqualTo(expected);
    }
}
