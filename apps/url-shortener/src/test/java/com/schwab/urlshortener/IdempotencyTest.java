package com.schwab.urlshortener;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.schwab.urlshortener.api.CreateLinkRequest;
import com.schwab.urlshortener.api.LinkResponse;
import com.schwab.urlshortener.application.IdempotencyService;
import com.schwab.urlshortener.application.LinkService;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest(properties = "shortener.analytics.enabled=false")
@AutoConfigureMockMvc
class IdempotencyTest extends UrlIntegrationTestSupport {
    @Autowired MockMvc client;
    @Autowired ObjectMapper json;
    @Autowired IdempotencyService idempotency;
    @Autowired LinkService service;

    @Test
    void sameKeyReplaysOriginalResponseAndDifferentPayloadConflicts() throws Exception {
        String body = "{\"url\":\"https://example.com/one\",\"customAlias\":\"same_key\"}";
        String original =
                client.perform(
                                post("/api/v1/links")
                                        .header("Idempotency-Key", "request-1")
                                        .contentType(MediaType.APPLICATION_JSON)
                                        .content(body))
                        .andExpect(status().isCreated())
                        .andReturn()
                        .getResponse()
                        .getContentAsString();
        JsonNode first = json.readTree(original);
        service.disable(first.get("shortCode").asText());
        String replay =
                client.perform(
                                post("/api/v1/links")
                                        .header("Idempotency-Key", "request-1")
                                        .contentType(MediaType.APPLICATION_JSON)
                                        .content(body))
                        .andExpect(status().isCreated())
                        .andReturn()
                        .getResponse()
                        .getContentAsString();
        assertThat(json.readTree(replay)).isEqualTo(first);
        client.perform(
                        post("/api/v1/links")
                                .header("Idempotency-Key", "request-1")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(
                                        "{\"url\":\"https://example.com/two\",\"customAlias\":\"same_key\"}"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("IDEMPOTENCY_CONFLICT"));
        assertThat(links.count()).isEqualTo(1);
        assertThat(records.count()).isEqualTo(1);
    }

    @Test
    void concurrentIdenticalRequestsCreateOnlyOneLink() throws Exception {
        CreateLinkRequest request =
                new CreateLinkRequest("https://example.com/concurrent", null, null);
        try (var pool = Executors.newFixedThreadPool(2)) {
            CountDownLatch start = new CountDownLatch(1);
            var first =
                    pool.submit(
                            () -> {
                                start.await();
                                return idempotency.create(request, "concurrent-key");
                            });
            var second =
                    pool.submit(
                            () -> {
                                start.await();
                                return idempotency.create(request, "concurrent-key");
                            });
            start.countDown();
            LinkResponse a = first.get(15, TimeUnit.SECONDS);
            LinkResponse b = second.get(15, TimeUnit.SECONDS);
            assertThat(a).isEqualTo(b);
        }
        assertThat(links.count()).isEqualTo(1);
        assertThat(records.count()).isEqualTo(1);
    }
}
