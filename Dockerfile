FROM python:3.12-slim-bookworm AS documentation
RUN apt-get update && apt-get install --no-install-recommends -y openjdk-17-jre-headless ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements-build.txt ./
RUN pip install --no-cache-dir -r requirements-build.txt
COPY tools/ tools/
COPY scripts/ scripts/
COPY schemas/ schemas/
RUN python scripts/install-allure.py --destination /opt/allure
COPY site/ site/
ARG MANIFEST_DIRECTORY=manifests
ARG ARTIFACT_DIRECTORY=build-input/cache
COPY ${MANIFEST_DIRECTORY}/ manifests/
COPY ${ARTIFACT_DIRECTORY}/ build-input/cache/
RUN python scripts/assemble.py --output /generated/site --allure /opt/allure/bin/allure

FROM nginxinc/nginx-unprivileged:stable-alpine AS runtime
USER 0:0
# Apply available distribution fixes even when the upstream tag has not rebuilt.
RUN apk upgrade --no-cache

ARG VCS_REF=local
ARG BUILD_DATE=local
LABEL org.opencontainers.image.title="ECommerceStore LiveDocs" \
      org.opencontainers.image.description="Static host for executable service documentation" \
      org.opencontainers.image.source="https://github.com/MichalBoczula/ECommerceStore.LiveDocs" \
      org.opencontainers.image.revision="$VCS_REF" \
      org.opencontainers.image.created="$BUILD_DATE"

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=documentation /generated/site/ /usr/share/nginx/html/
# SHA/date values are supplied by CI; JSON is served as deployment identity.
RUN printf '{"commitSha":"%s","builtAt":"%s"}\n' "$VCS_REF" "$BUILD_DATE" \
      > /usr/share/nginx/html/build-info.json

USER 101:101
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/health/ready || exit 1
