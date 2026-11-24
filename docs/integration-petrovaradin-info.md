# Future integration with Petrovaradin.info

- **Backend API.** Expose the contract under `/api/v1`, with structured citations and explicit answers about evidence availability. The site can use a reverse proxy or connect directly with restricted CORS.
- **Embedded interface.** Show the answer, disagreements, and citations. Let readers choose Serbian Latin or Cyrillic and retain the original script in marked quotations.
- **Source links.** Include a source identifier and a page or folio locator. Link to an authorized record or passage where available. For restricted material, show the bibliography and archive reference.
- **Expert review.** An editor interface could show passages and record assessments, names, dates, and revision history. Editorial operations require authentication and the appropriate role.
- **Caching and abuse prevention.** Key cached answers by language, script, corpus version, and answer contract. Limit request frequency, input length, and generation cost. Store keys on the server. Treat instructions in source material as data. Restrict access to content and logs according to rights and purpose.

See [architecture and operations](architecture.md) for implemented endpoints and deployment requirements.
