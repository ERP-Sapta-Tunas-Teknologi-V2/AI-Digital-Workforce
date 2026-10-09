# CORS Policy

## Objective

Membatasi akses cross-origin API chatbot hanya dari domain frontend perusahaan yang telah diizinkan.

## Allowed Origins

API hanya mengizinkan origin yang terdapat dalam whitelist:

```text
http://localhost:5173
https://2023.smartindo.com
```

> ⚠️ **Catatan implementasi:** `ALLOWED_ORIGINS` di-hardcode pada `app.py`. `http://localhost:5173` (development) harus dihapus sebelum production.

Origin development tidak boleh digunakan pada konfigurasi production.

## API Scope

CORS diterapkan pada endpoint API:

```text
/api/*
```

## Allowed Methods

CORS diterapkan pada seluruh `/api/*` (Flask-CORS default: GET, POST, PUT, PATCH, DELETE, OPTIONS). Pembatasan method per endpoint dilakukan oleh route masing-masing.

Preflight `OPTIONS` digunakan oleh browser apabila diperlukan. Frontend Vue mengirim header kustom `X-User-Role`, sehingga request lintas-origin selalu memicu preflight (Flask-CORS secara default mengizinkan header request apa pun).

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
Origin: https://2023.smartindo.com
```

Expected:

```text
Access-Control-Allow-Origin: https://2023.smartindo.com
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
Origin: https://2023.smartindo.com
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
