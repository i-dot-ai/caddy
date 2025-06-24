FROM opensearchproject/opensearch:3

RUN /usr/share/opensearch/bin/opensearch-plugin remove opensearch-security
RUN /usr/share/opensearch/bin/opensearch-plugin remove opensearch-performance-analyzer
