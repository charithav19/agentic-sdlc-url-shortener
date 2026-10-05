package com.schwab.urlshortener;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.schwab.urlshortener.application.LinkService;
import com.schwab.urlshortener.application.RedirectService;
import com.schwab.urlshortener.domain.Link;
import com.schwab.urlshortener.domain.ShortCodeGenerator;
import com.schwab.urlshortener.persistence.LinkRepository;
import java.util.Optional;
import org.junit.jupiter.api.Test;

class CoreRegressionTest {
    @Test
    void existingCreateBehaviorUsesGeneratedCode() {
        var repository = mock(LinkRepository.class);
        var generator = mock(ShortCodeGenerator.class);
        when(generator.nextCode()).thenReturn("Ab3xYz9");
        when(repository.save(org.mockito.ArgumentMatchers.any(Link.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        var link = new LinkService(repository, generator).create("https://example.com");
        assertEquals("Ab3xYz9", link.getShortCode());
    }

    @Test
    void existingRedirectLookupReturnsOriginalUrl() {
        var repository = mock(LinkRepository.class);
        when(repository.findByShortCode("Ab3xYz9"))
                .thenReturn(Optional.of(new Link("https://example.com", "Ab3xYz9")));
        var link = new RedirectService(repository).resolve("Ab3xYz9");
        assertEquals("https://example.com", link.getOriginalUrl());
    }
}
