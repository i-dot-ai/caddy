FROM mwendler/figlet

RUN mkdir /app
WORKDIR /app

COPY welcome.sh welcome.sh
COPY future.tlf future.tlf
RUN chmod +x welcome.sh

ENTRYPOINT ["./welcome.sh"]
