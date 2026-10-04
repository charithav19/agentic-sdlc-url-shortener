package com.schwab.urlshortener;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.schwab.urlshortener.application.LinkService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest(properties = "shortener.analytics.enabled=false")
@AutoConfigureMockMvc
class AliasTest extends UrlIntegrationTestSupport {
    @Autowired MockMvc client;
    @Autowired LinkService service;

    @Test
    void acceptsBoundariesAndPreservesCase() {
        service.create("https://example.com/one", "Ab3", null);
        service.create("https://example.com/two", "a".repeat(32), null);
        service.create("https://example.com/three", "ab_-XYZ", null);
        service.create("https://example.com/four", "ab3", null);
        assertThat(links.count()).isEqualTo(4);
    }

    @Test
    void invalidAndReservedAliasesReturn400() throws Exception {
        for (String alias :
                new String[] {
                    "ab",
                    "a".repeat(33),
                    "bad.alias",
                    "API",
                    "Actuator",
                    "SWAGGER-UI",
                    "v3",
                    "HEALTH"
                }) {
            client.perform(
                            post("/api/v1/links")
                                    .contentType(MediaType.APPLICATION_JSON)
                                    .content(
                                            "{\"url\":\"https://example.com\",\"customAlias\":\""
                                                    + alias
                                                    + "\"}"))
                    .andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.code").value("INVALID_ALIAS"));
        }
        assertThat(links.count()).isZero();
    }

    @Test
    void duplicateAliasReturns409WithoutAnotherRow() throws Exception {
        service.create("https://example.com/first", "my_alias", null);
        client.perform(
                        post("/api/v1/links")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(
                                        "{\"url\":\"https://example.com/second\",\"customAlias\":\"my_alias\"}"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("ALIAS_CONFLICT"));
        assertThat(links.count()).isEqualTo(1);
    }
}
