# elclavo.gastromanager.es — Web Next (/) + Gastro (/panel, /login, …)
# Puertos Docker Clavo: web 37891, gastro 37892

upstream clavo_next_elclavo {
    server 127.0.0.1:37891;
    keepalive 16;
}

upstream clavo_gastro_elclavo {
    server 127.0.0.1:37892;
    keepalive 16;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name elclavo.gastromanager.es;

    ssl_certificate     /etc/letsencrypt/live/elclavo.gastromanager.es/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/elclavo.gastromanager.es/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size 25M;
    include /etc/nginx/snippets/letsencrypt-acme-noauth.conf;

    # ---------- Gastro (Flask) ----------
    location ^~ /panel {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /login {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /login_empleado {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /login_cliente {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /logout {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location = /verificar_admin {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /acceso-interno {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /set_lang/ {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /visualizar {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /static/ {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location = /sw.js {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /confirmar-reserva {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /tablet/ {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }

    location ^~ /reservas {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /inventario {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /empleados {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /clientes {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /proveedores {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /horarios {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /horario/ {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /calendario {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /cierre_caja {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /configuracion_tablet {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /configuracion_pin_tablet {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /configuracion_empresa {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /configuracion_reservas_web {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /fichajes {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /fichaje {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /fichar {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /confirmar_fichaje {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /libro_firmas {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /pdf_trabajador {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /generar_pdf_mensual {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /chat {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /rrhh_peticiones {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /escandallos {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /vacaciones_jornada {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /area_personal {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /peticiones_rrhh {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /panel_empleado {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /buscar_global {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /rangos_permisos {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /mi_horario_pdf/ {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /conformidad_jornada {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /crear_empleado {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /actualizar_empleado/ {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /eliminar_empleado/ {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /editar_salon {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /mover_objeto {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /actualizar_objeto {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /crear_objeto {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /eliminar_mesa/ {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /vaciar_esquema/ {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /editar/ {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /crear {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /actualizar/ {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /estado/ {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /eliminar/ {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /generar_horarios_reglas {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /empleado/ {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /crear_solicitud {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /rrhh_chat {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
    location ^~ /reserva_autorizada {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }

    # Incluye reserva_rapida (alta desde sala / panel); sin esto Next devuelve 404 en el mismo host.
    location ~ ^/api/(web/|sala_vivo|salones|salon/|esquema|esquemas|busqueda|reserva/|reserva_rapida|empleado/|ocupacion_mesas|sugerencias_union_mesa|sala_mesas_opciones|reserva_estado|walkin|asignar_mesa_reserva|union_mesas|clientes/|calendario_eventos) {
        proxy_pass http://clavo_gastro_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }

    location = /tablet {
        return 301 /recepcion;
    }

    location / {
        proxy_pass http://clavo_next_elclavo;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
}

server {
    listen 80;
    listen [::]:80;
    server_name elclavo.gastromanager.es;
    return 301 https://elclavo.gastromanager.es$request_uri;
}
