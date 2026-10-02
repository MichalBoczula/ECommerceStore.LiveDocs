FROM nginxinc/nginx-unprivileged:stable-alpine
USER 0:0

ARG VCS_REF=local
ARG BUILD_DATE=local
LABEL org.opencontainers.image.title="ECommerceStore LiveDocs" \
      org.opencontainers.image.description="Static host for executable service documentation" \
      org.opencontainers.image.source="https://github.com/MichalBoczula/ECommerceStore.LiveDocs" \
      org.opencontainers.image.revision="$VCS_REF" \
      org.opencontainers.image.created="$BUILD_DATE"

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY site/ /usr/share/nginx/html/
# SHA/date values are supplied by CI; JSON is served as deployment identity.
RUN printf '{"commitSha":"%s","builtAt":"%s"}\n' "$VCS_REF" "$BUILD_DATE" \
      > /usr/share/nginx/html/build-info.json

USER 101:101
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/health/ready || exit 1
