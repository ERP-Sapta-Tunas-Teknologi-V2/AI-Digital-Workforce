# CORS Policy

## Objective

Membatasi akses cross-origin API chatbot hanya dari domain frontend perusahaan yang telah diizinkan.

## Allowed Origins

API hanya mengizinkan origin yang terdapat dalam whitelist:

```text
https://saptatunas.com
```

Development dapat menggunakan origin localhost jika diperlukan:

```text
http://localhost:3000
```

Origin development tidak boleh digunakan pada konfigurasi production.

## API Scope

CORS diterapkan pada endpoint API:

```text
/api/*
```

## Allowed Methods

API hanya mengizinkan HTTP methods yang digunakan oleh application.

Untuk chatbot:

```text
POST /api/chat
```

Preflight `OPTIONS` digunakan oleh browser apabila diperlukan.

## Disallowed Origins

Origin yang tidak terdapat dalam whitelist tidak mendapatkan:

```text
Access-Control-Allow-Origin
```

Browser akan memblokir akses frontend terhadap response API tersebut.

## Security

CORS bukan authentication atau authorization.

CORS hanya mengontrol akses cross-origin yang dilakukan oleh browser.

Request langsung menggunakan tools seperti curl, Postman, atau Python tetap dapat mencapai API apabila endpoint tidak memiliki mekanisme authentication atau access control lainnya.

## Testing

### Allowed Origin

```text
Origin: https://saptatunas.com
```

Expected:

```text
Access-Control-Allow-Origin: https://saptatunas.com
```

### Disallowed Origin

Contoh:

```text
Origin: https://evil.com
```

Expected:

```text
Access-Control-Allow-Origin: None
```

Browser harus memblokir akses frontend terhadap response dari origin tersebut.

### Preflight

Request:

```text
OPTIONS /api/chat
Origin: https://saptatunas.com
Access-Control-Request-Method: POST
```

Expected preflight response memiliki CORS headers yang sesuai dengan whitelist.

## Production Consideration

Whitelist production harus hanya berisi domain frontend perusahaan yang resmi.

Wildcard:

```text
*
```

tidak diperbolehkan untuk production.

CORS tidak boleh digunakan sebagai pengganti authentication atau authorization.
