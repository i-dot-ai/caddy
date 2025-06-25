FROM opensearchproject/opensearch:3.1.0

RUN /usr/share/opensearch/bin/opensearch-plugin remove opensearch-anomaly-detection
RUN /usr/share/opensearch/bin/opensearch-plugin remove opensearch-security
RUN /usr/share/opensearch/bin/opensearch-plugin remove opensearch-performance-analyzer
