# Quay Image Expiration

Python script to change the image lifetime in the [Quay][] container registry.
Allows you to set different lifetimes for different tags according to a regular
expression. Will not change existing TTL labels.

![demo](extras/quay-expiration.gif)

Add this script to your scheduler (crontab, systemd timer, kubernetes cronJo
or similar) and keep your container registry clean. No more junk tags,
intermediate versions live for a limited time, only releases stay forever.

> Quay has support for the `quay.expires-after` label which allows you to set
> the lifetime of an artifact at the build stage in your CI pipeline.
> But not all good fellows use it, that's why this script appeared, for total
> control over the lifetime of images.

## Configuration

* **`QUAY_URL`** - URL of Quay instance.  
  Takes precedence over YAML configuration key `quay.url` and it's the same.
* **`QUAY_TOKEN`** - Token with owner or admin permissions for change
  expiration.  
  Takes precedence over YAML configuration key `quay.token` and it's the same.
* **`QUAY_DRY_RUN`**=`False` - Test run script for review,
  will not change anything.  
  Takes precedence over YAML configuration key `quay.dry_run` and it's the same.
* **`QUAY_IMAGE_EXPIRE`**=`336h` - Default image expiration time.  
  Takes precedence over YAML configuration key `quay.default_expiration`
  and it's the same.

Default config stored in [`config.yml`](config.yml)

```yml
quay:
  url:  # URL of Quay instance
  token:  # Token with owner or admin permissions for change expiration
  dry_run: false # Test run script for review, will not change anything.
  exclude_projects: # List of ignored projects
    - group/project
  default_expiration: 336h  # Default image expiration time.
  expiration:   # Regex rules for tags and expiration time for matches
    - name: release
      regex: ^(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*)){2}$
      expire: 0s
    - name: double release
      regex: ^(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*)){2}(-(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*)){2})$
      expire: 0s
    - name: latest
      regex: ^latest((\+|-)[0-9A-Za-z\.-]+){0,2}$
      expire: 0s
    - name: meta release
      regex: ^(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*)){2}((\+|-)[0-9A-Za-z\.-]+){1,3}$
      expire: 336h
    - name: development
      regex: ^(dev(el(op(ment)?)?)?|[0-9a-zA-Z-]*-rc)$
      expire: 192h

```

## Exclude projects

Whatever the lifetime of the project/tag is not changed:

* The tag must already have a lifetime, by setting 999 years you explicitly
  tell it to live long, long enough I guess.
* The tag must match the regular expression where the time is set to
  `expire: 0s` - this means the tag will not disappear.
* Add projects to the `exclude_projects` list of the configuration and they
  will be skipped in the analysis.

## Container Image

* [`docker pull ghcr.io/woozymasta/quay-expiration:latest`](https://github.com/WoozyMasta/quay-expirationp/pkgs/container/quay-expiration)
* [`docker pull quay.io/woozymasta/quay-expiration:latest`](https://quay.io/repository/woozymasta/quay-expiration)
* [`docker pull docker.io/woozymasta/quay-expiration:latest`](https://hub.docker.com/r/woozymasta/quay-expiration)

```bash
docker run --rm -ti \
  -e "QUAY_URL=https://quay.tld.local" \
  -e "QUAY_TOKEN=XXXXXXXX" \
  -e "QUAY_DRY_RUN=true" \
  -v "$(pwd):/app/config.yml" \
  ghcr.io/woozymasta/quay-expiration:latest
```

## Running code locally from a repo

```bash
python -m venv .venv
. ./.venv/bin/activate
cp .env.example .env
editor .env
editor config.yml
./expiration.py
```

[Quay]: https://www.projectquay.io
