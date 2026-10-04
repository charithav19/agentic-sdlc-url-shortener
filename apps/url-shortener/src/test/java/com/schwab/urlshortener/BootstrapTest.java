package com.schwab.urlshortener;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class BootstrapTest {
    @Autowired private MockMvc client;

    @Test
    void bootsWithoutProductEndpoints() throws Exception {
        client.perform(get("/api/v1/links")).andExpect(status().isNotFound());
    }

    @Test
    void doesNotProvideRedirectFunctionality() throws Exception {
        client.perform(get("/example")).andExpect(status().isNotFound());
    }
}
