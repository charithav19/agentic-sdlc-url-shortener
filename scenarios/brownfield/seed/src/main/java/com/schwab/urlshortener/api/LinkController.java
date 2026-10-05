package com.schwab.urlshortener.api;

import com.schwab.urlshortener.application.LinkService;
import io.swagger.v3.oas.annotations.Operation;
import java.net.URI;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/links")
public class LinkController {
    private final LinkService service;

    public LinkController(LinkService service) {
        this.service = service;
    }

    @Operation(summary = "Create a random short link")
    @PostMapping
    public ResponseEntity<LinkResponse> create(@RequestBody CreateLinkRequest request) {
        var link = service.create(request.url());
        return ResponseEntity.created(URI.create("/api/v1/links/" + link.getShortCode()))
                .body(new LinkResponse(link.getShortCode(), link.getOriginalUrl()));
    }

    public record CreateLinkRequest(String url) {}
    public record LinkResponse(String shortCode, String url) {}
}
