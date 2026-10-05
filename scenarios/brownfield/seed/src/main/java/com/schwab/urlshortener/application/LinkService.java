package com.schwab.urlshortener.application;

import com.schwab.urlshortener.domain.Link;
import com.schwab.urlshortener.domain.ShortCodeGenerator;
import com.schwab.urlshortener.persistence.LinkRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class LinkService {
    private final LinkRepository repository;
    private final ShortCodeGenerator generator;

    public LinkService(LinkRepository repository, ShortCodeGenerator generator) {
        this.repository = repository;
        this.generator = generator;
    }

    @Transactional
    public Link create(String originalUrl) {
        return repository.save(new Link(originalUrl, generator.nextCode()));
    }
}
