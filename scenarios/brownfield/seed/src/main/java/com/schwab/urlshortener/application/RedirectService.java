package com.schwab.urlshortener.application;

import com.schwab.urlshortener.domain.Link;
import com.schwab.urlshortener.persistence.LinkRepository;
import org.springframework.stereotype.Service;

@Service
public class RedirectService {
    private final LinkRepository repository;

    public RedirectService(LinkRepository repository) {
        this.repository = repository;
    }

    public Link resolve(String shortCode) {
        return repository.findByShortCode(shortCode)
                .orElseThrow(() -> new LinkNotFoundException(shortCode));
    }

    public static class LinkNotFoundException extends RuntimeException {
        public LinkNotFoundException(String shortCode) {
            super("Unknown short code: " + shortCode);
        }
    }
}
