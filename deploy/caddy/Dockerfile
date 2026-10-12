FROM golang:1.27.2-alpine@sha256:f92b6ef800e499660581efdabdf25d9d817a9d124eaf900924f0504e7e27e12d AS build
ENV GOMAXPROCS=2
WORKDIR /src
COPY main.go go.mod go.sum ./
RUN go mod download \
    && CGO_ENABLED=0 go build -p 2 -mod=readonly -trimpath -o /out/caddy .

FROM caddy:2.11.7-alpine@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f
RUN apk upgrade --no-cache
COPY --from=build /out/caddy /usr/bin/caddy
