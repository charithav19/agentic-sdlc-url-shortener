package com.schwab.urlshortener;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.schwab.urlshortener.persistence.LinkRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.postgresql.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

@Testcontainers
@SpringBootTest(properties = "shortener.analytics.enabled=false")
@AutoConfigureMockMvc
class LinkApiTest {
    private static final String POSTGRES_IMAGE =
            "postgres:17.7-alpine@sha256:bb377b7239d2774ac8cc76f481596ce96c5a6b5e9d141f6d0a0ee371a6e7c0f2";

    @Container
    static final PostgreSQLContainer postgres =
            new PostgreSQLContainer(
                    DockerImageName.parse(POSTGRES_IMAGE).asCompatibleSubstituteFor("postgres"));

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @Autowired private MockMvc client;
    @Autowired private ObjectMapper json;
    @Autowired private LinkRepository links;

    @BeforeEach
    void clearLinks() {
        links.deleteAll();
    }

    @Test
    void createMetadataAndRedirectRoundTrip() throws Exception {
        MvcResult created =
                client.perform(
                                post("/api/v1/links")
                                        .contentType(MediaType.APPLICATION_JSON)
                                        .content("{\"url\":\"https://example.com/a?b=c\"}"))
                        .andExpect(status().isCreated())
                        .andExpect(jsonPath("$.url").value("https://example.com/a?b=c"))
                        .andExpect(jsonPath("$.status").value("ACTIVE"))
                        .andExpect(jsonPath("$.id").isNotEmpty())
                        .andExpect(jsonPath("$.createdAt").isNotEmpty())
                        .andExpect(jsonPath("$.expiresAt").value(org.hamcrest.Matchers.nullValue()))
                        .andReturn();
        JsonNode body = json.readTree(created.getResponse().getContentAsString());
        String code = body.get("shortCode").asText();
        assertThat(code).matches("[0-9A-Za-z]{7}");
        assertThat(body.get("shortUrl").asText()).isEqualTo("http://localhost:8080/" + code);
        assertThat(created.getResponse().getHeader("Location"))
                .isEqualTo(body.get("shortUrl").asText());
        assertThat(links.count()).isEqualTo(1);

        client.perform(get("/api/v1/links/{code}", code))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.shortCode").value(code));
        client.perform(get("/{code}", code))
                .andExpect(status().isFound())
                .andExpect(header().string("Location", "https://example.com/a?b=c"));
        assertThat(links.count()).isEqualTo(1);
    }

    @Test
    void unknownCodeReturnsStructured404WithTraceId() throws Exception {
        for (String path : new String[] {"/api/v1/links/unknown", "/unknown"}) {
            MvcResult result =
                    client.perform(get(path))
                            .andExpect(status().isNotFound())
                            .andExpect(jsonPath("$.code").value("LINK_NOT_FOUND"))
                            .andExpect(jsonPath("$.traceId").isNotEmpty())
                            .andReturn();
            JsonNode body = json.readTree(result.getResponse().getContentAsString());
            assertThat(result.getResponse().getHeader("X-Trace-Id"))
                    .isEqualTo(body.get("traceId").asText());
        }
    }

    @Test
    void invalidAndUnsupportedInputsReturn400WithoutCreatingLinks() throws Exception {
        for (String body :
                new String[] {
                    "{\"url\":\"ftp://example.com\"}",
                    "{\"url\":\"https://user:pass@example.com\"}",
                    "{\"url\":\"\"}",
                    "{\"url\":\"https://example.com\",\"customAlias\":\"bad alias\"}",
                    "{\"url\":\"https://example.com\",\"expiresAt\":\"2020-01-01T00:00:00Z\"}"
                }) {
            client.perform(
                            post("/api/v1/links")
                                    .contentType(MediaType.APPLICATION_JSON)
                                    .content(body))
                    .andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.code").isNotEmpty());
        }
        assertThat(links.count()).isZero();
    }

    @Test
    void openApiAndHealthAreAvailableWithoutSensitiveActuatorEndpoints() throws Exception {
        client.perform(get("/v3/api-docs"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.paths['/api/v1/links'].post").exists())
                .andExpect(jsonPath("$.paths['/{shortCode}'].get").exists());
        client.perform(get("/actuator/health")).andExpect(status().isOk());
        client.perform(get("/actuator/env")).andExpect(status().isNotFound());
    }
}
