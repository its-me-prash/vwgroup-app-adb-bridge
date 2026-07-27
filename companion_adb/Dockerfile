ARG BUILD_FROM
FROM ${BUILD_FROM}

# android-tools provides the real `adb` binary (with Android 11+ pairing/TLS).
# If a given base image's android-tools is ever too old for pairing, swap this
# for a pinned platform-tools download for the target arch.
# py3-zeroconf powers mDNS auto-discovery of the (ephemeral) wireless-debugging
# port; it is best-effort, so the build never fails if the package is missing —
# the add-on then falls back to the configured connect_address.
RUN apk add --no-cache android-tools python3 \
 && (apk add --no-cache py3-zeroconf || echo "py3-zeroconf unavailable; mDNS discovery disabled")

COPY bridge.py /bridge.py
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
