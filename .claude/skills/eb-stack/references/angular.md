# Referencia — Frontend (Angular 19)

## Tabla de contenidos

1. Plantilla de service con caché
2. Plantilla de component (standalone)
3. Interceptor JWT
4. Guard de ruta
5. Proxy y `environment`
6. Manejo de suscripciones
7. Checklist antes de cerrar un cambio

## 1. Plantilla de service con caché

Sigue el patrón real de `src/app/services/monitor-odoo.service.ts`.

```typescript
// src/app/services/<dominio>.service.ts
import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, BehaviorSubject, of, throwError } from 'rxjs';
import { tap, shareReplay, catchError } from 'rxjs/operators';
import { environment } from '../../environments/environment';

export interface <Dominio> {
  id: number;
  nombre: string;
}

@Injectable({ providedIn: 'root' })
export class <Dominio>Service {
  private apiUrl = `${environment.apiUrl}`;

  // Caché local con BehaviorSubject: emite el último valor y permite invalidar.
  private dataCache = new BehaviorSubject<<Dominio>[] | null>(null);

  constructor(private http: HttpClient) {}

  /** Precarga silenciosa — útil para invocar al iniciar una vista. */
  precargar(): void {
    if (this.dataCache.value) return;
    this.listar().subscribe();
  }

  listar(): Observable<<Dominio>[]> {
    if (this.dataCache.value) {
      return of(this.dataCache.value);
    }
    return this.http.get<<Dominio>[]>(`${this.apiUrl}/<dominio>`).pipe(
      tap(data => this.dataCache.next(data)),
      catchError(this.handleError),
    );
  }

  crear(payload: Partial<<Dominio>>): Observable<<Dominio>> {
    return this.http.post<<Dominio>>(`${this.apiUrl}/<dominio>`, payload).pipe(
      tap(() => this.dataCache.next(null)), // invalida caché
      catchError(this.handleError),
    );
  }

  private handleError(err: HttpErrorResponse) {
    const mensaje = err.error?.error || 'Error de red, intenta de nuevo';
    return throwError(() => new Error(mensaje));
  }
}
```

**Notas:**
- `providedIn: 'root'` hace el service singleton sin registrarlo en un module.
- `environment.apiUrl` debe estar en `src/environments/environment.ts` (dev) y `environment.prod.ts` (build producción).
- El proxy dev rescribe `/api` → `http://127.0.0.1:5000` (ver `proxy.conf.json`). En dev pon `apiUrl: '/api'`; en prod pon la URL absoluta del backend.

## 2. Plantilla de component (standalone)

```typescript
// src/app/views/<dominio>/<dominio>.component.ts
import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { Subject, takeUntil } from 'rxjs';

import { <Dominio>Service, <Dominio> } from '../../services/<dominio>.service';

@Component({
  selector: 'app-<dominio>',
  standalone: true,
  imports: [CommonModule, MatTableModule, MatButtonModule],
  templateUrl: './<dominio>.component.html',
  styleUrl: './<dominio>.component.css',
})
export class <Dominio>Component implements OnInit, OnDestroy {
  registros: <Dominio>[] = [];
  cargando = false;
  error: string | null = null;

  private destroy$ = new Subject<void>();

  constructor(private svc: <Dominio>Service) {}

  ngOnInit(): void {
    this.cargar();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  cargar(): void {
    this.cargando = true;
    this.error = null;
    this.svc.listar()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: data => { this.registros = data; this.cargando = false; },
        error: e => { this.error = e.message; this.cargando = false; },
      });
  }
}
```

**Preferencia:** cuando la plantilla solo muestra datos, usa `async` pipe y evita `subscribe` manual:

```html
<table *ngIf="registros$ | async as registros" mat-table [dataSource]="registros">
  ...
</table>
```

## 3. Interceptor JWT

Agrega automáticamente el header `Authorization: Bearer <token>` a toda llamada HTTP.

```typescript
// src/app/interceptors/jwt.interceptor.ts
import { HttpInterceptorFn } from '@angular/common/http';

export const jwtInterceptor: HttpInterceptorFn = (req, next) => {
  const token = localStorage.getItem('token');
  if (token) {
    req = req.clone({
      setHeaders: { Authorization: `Bearer ${token}` },
    });
  }
  return next(req);
};
```

Regístralo en `app.config.ts`:

```typescript
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { jwtInterceptor } from './interceptors/jwt.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideHttpClient(withInterceptors([jwtInterceptor])),
    // ...
  ],
};
```

## 4. Guard de ruta

```typescript
// src/app/guards/auth.guard.ts
import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';
import { jwtDecode } from 'jwt-decode';

export const authGuard: CanActivateFn = (route, state) => {
  const router = inject(Router);
  const token = localStorage.getItem('token');
  if (!token) {
    router.navigate(['/login']);
    return false;
  }
  try {
    const payload = jwtDecode<{ exp: number }>(token);
    if (payload.exp * 1000 < Date.now()) {
      localStorage.removeItem('token');
      router.navigate(['/login']);
      return false;
    }
    return true;
  } catch {
    router.navigate(['/login']);
    return false;
  }
};
```

Uso en `app.routes.ts`:

```typescript
{ path: 'dashboard', component: DashboardComponent, canActivate: [authGuard] }
```

## 5. Proxy y `environment`

`proxy.conf.json` (ya existe):

```json
{
  "/api": {
    "target": "http://127.0.0.1:5000",
    "secure": false,
    "changeOrigin": true,
    "pathRewrite": { "^/api": "" },
    "logLevel": "info"
  }
}
```

`src/environments/environment.ts` (desarrollo):
```typescript
export const environment = {
  production: false,
  apiUrl: '/api',
};
```

`src/environments/environment.prod.ts`:
```typescript
export const environment = {
  production: true,
  apiUrl: 'https://api.elite-bike.com',
};
```

## 6. Manejo de suscripciones

Tres opciones, de preferida a menos preferida:

1. **`async` pipe en plantilla** — Angular se encarga de desuscribir. Óptimo cuando solo consumes el valor en la vista.
2. **`takeUntil(destroy$)`** — patrón del ejemplo de arriba. Usa cuando necesitas reaccionar a la emisión fuera de la plantilla.
3. **Guardar `Subscription` y `unsubscribe()` en `ngOnDestroy`** — legacy, funciona pero es fácil olvidar una.

Nunca dejes una suscripción sin destruir en components que entran/salen del DOM — causa fugas y callbacks duplicados.

## 7. Checklist antes de cerrar un cambio

- [ ] Service tiene `.spec.ts` con `HttpClientTestingModule`
- [ ] Component con lógica no trivial tiene `.spec.ts`
- [ ] Respuestas HTTP están tipadas con interface (no `any`)
- [ ] `environment.apiUrl` usado (no URL hardcodeada)
- [ ] Suscripciones manuales se destruyen en `ngOnDestroy`
- [ ] Errores HTTP se manejan (interceptor global o `catchError` local)
- [ ] No hay `console.log` residuales
- [ ] `ng test --watch=false` pasa
- [ ] `ng build` compila sin warnings nuevos
