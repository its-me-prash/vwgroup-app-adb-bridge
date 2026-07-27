ARG BUILD_FROM
FROM ${BUILD_FROM}

# android-tools provides the real `adb` binary (with Android 11+ pairing/TLS).
# If a given base image's android-tools is ever too old for pairing, swap this
# for a pinned platform-tools download for the target arch.
RUN apk add --no-cache android-tools python3

COPY bridge.py /bridge.py
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
