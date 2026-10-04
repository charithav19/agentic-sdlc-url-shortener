package com.schwab.urlshortener.api;

import com.schwab.urlshortener.application.IdempotencyService;
import com.schwab.urlshortener.application.LinkService;
import com.schwab.urlshortener.config.ShortUrlProperties;
import jakarta.validation.Valid;
import java.net.URI;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/links")
public class LinkController {
    private final LinkService service;
    private final IdempotencyService idempotency;
    private final ShortUrlProperties urls;

    public LinkController(
            LinkService service, IdempotencyService idempotency, ShortUrlProperties urls) {
        this.service = service;
        this.idempotency = idempotency;
        this.urls = urls;
    }

    @PostMapping
    public ResponseEntity<LinkResponse> create(
            @Valid @RequestBody CreateLinkRequest request,
            @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey) {
        LinkResponse response = idempotency.create(request, idempotencyKey);
        return ResponseEntity.created(URI.create(response.shortUrl())).body(response);
    }

    @GetMapping("/{shortCode}")
    public LinkResponse metadata(@PathVariable String shortCode) {
        return LinkResponse.from(service.findByCode(shortCode), urls);
    }

    @DeleteMapping("/{shortCode}")
    public ResponseEntity<Void> disable(@PathVariable String shortCode) {
        service.disable(shortCode);
        return ResponseEntity.noContent().build();
    }
}
