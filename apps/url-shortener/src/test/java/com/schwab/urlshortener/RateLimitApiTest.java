package com.schwab.urlshortener;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest(
        properties = {
            "shortener.rate-limit.capacity=2",
            "shortener.rate-limit.window=1m",
            "shortener.analytics.enabled=false"
        })
@AutoConfigureMockMvc
class RateLimitApiTest extends UrlIntegrationTestSupport {
    @Autowired MockMvc client;

    @Test
    void createRouteReturns429AndRetryAfter() throws Exception {
        for (int i = 0; i < 2; i++) {
            client.perform(
                            post("/api/v1/links")
                                    .contentType(MediaType.APPLICATION_JSON)
                                    .content("{\"url\":\"https://example.com/" + i + "\"}"))
                    .andExpect(status().isCreated());
        }
        client.perform(
                        post("/api/v1/links")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"url\":\"https://example.com/blocked\"}"))
                .andExpect(status().isTooManyRequests())
                .andExpect(header().exists("Retry-After"))
                .andExpect(jsonPath("$.code").value("RATE_LIMITED"));
    }
}
