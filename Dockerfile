# SpeedBox - Docker Image
# Licence: AGPL-3.0-only
#
# Build:  docker build -t speedbox .
# Run:    docker run -d --name speedbox --net=host --privileged speedbox
#
# Note: --net=host est recommande pour acceder aux interfaces reseau du host.
#       --privileged est necessaire pour les commandes reseau (ip, ethtool, etc.)
#       Sans --privileged, les fonctions de configuration reseau seront desactivees.

FROM python:3.13-slim-bookworm

LABEL maintainer="slalanne"
LABEL description="SpeedBox - Network testing and diagnostics web application"
LABEL license="AGPL-3.0-only"

# Paquets systeme pour les outils reseau
RUN apt-get update && apt-get install -y --no-install-recommends \
    iperf3 \
    mtr-tiny \
    traceroute \
    ethtool \
    dnsutils \
    iproute2 \
    net-tools \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/speedbox

# Copier requirements et installer les deps Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY app.py .
COPY servers.json .
COPY config/public_servers.json config/
COPY static/ static/
COPY templates/ templates/

# Creer les repertoires de donnees
RUN mkdir -p config results

# Volumes pour la persistance des donnees
VOLUME ["/opt/speedbox/config", "/opt/speedbox/results"]

# Port par defaut
EXPOSE 5000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/status')" || exit 1

# Demarrage
CMD ["python", "app.py"]
