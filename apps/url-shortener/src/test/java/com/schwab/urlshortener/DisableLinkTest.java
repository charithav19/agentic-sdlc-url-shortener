package com.schwab.urlshortener;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.schwab.urlshortener.application.LinkService;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest(properties = "shortener.analytics.enabled=false")
@AutoConfigureMockMvc
class DisableLinkTest extends UrlIntegrationTestSupport {
    @Autowired MockMvc client;
    @Autowired LinkService service;

    @Test
    void repeatableDisableReturns204AndRedirectReturns410() throws Exception {
        String code = service.create("https://example.com/a", "to_disable", null).getShortCode();
        client.perform(delete("/api/v1/links/{code}", code)).andExpect(status().isNoContent());
        client.perform(delete("/api/v1/links/{code}", code)).andExpect(status().isNoContent());
        client.perform(get("/{code}", code))
                .andExpect(status().isGone())
                .andExpect(jsonPath("$.code").value("LINK_GONE"));
        client.perform(delete("/api/v1/links/missing")).andExpect(status().isNotFound());
    }

    @Test
    void concurrentDisableDoesNotLoseOrFailMutation() throws Exception {
        String code =
                service.create("https://example.com/a", "concurrent_disable", null).getShortCode();
        try (var pool = Executors.newFixedThreadPool(2)) {
            CountDownLatch start = new CountDownLatch(1);
            var first =
                    pool.submit(
                            () -> {
                                start.await();
                                service.disable(code);
                                return true;
                            });
            var second =
                    pool.submit(
                            () -> {
                                start.await();
                                service.disable(code);
                                return true;
                            });
            start.countDown();
            assertThat(first.get(10, TimeUnit.SECONDS)).isTrue();
            assertThat(second.get(10, TimeUnit.SECONDS)).isTrue();
        }
        client.perform(get("/{code}", code)).andExpect(status().isGone());
    }
}
