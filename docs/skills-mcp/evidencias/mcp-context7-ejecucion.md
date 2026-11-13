# Evidencia de ejecución MCP — Context7 (`@upstash/context7-mcp`)

- **Fecha**: 2026-11-13
- **Cliente/Configuración**: `opencode.json` en la raíz del repositorio (`type: "local"`, `command: ["npx", "-y", "@upstash/context7-mcp"]`, sin secretos)
- **Servidor conectado**: `Context7 Documentation MCP Server v4.7.0` (protocolo `2024-11-05`, transporte `stdio`)

## 1. Solicitud realizada

Durante la preparación técnica de **`C-10` (`frontend-reserva-publica`)** se ejecutó una sesión real por `stdio` contra `@upstash/context7-mcp` enviando:

1. `initialize`
2. `tools/list`
3. `tools/call` → `resolve-library-id`:
   ```json
   {
     "libraryName": "react-router",
     "query": "useSearchParams routes in react-router-dom v6"
   }
   ```
4. `tools/call` → `query-docs`:
   ```json
   {
     "libraryId": "/remix-run/react-router",
     "query": "useSearchParams reading search params token"
   }
   ```

## 2. Resultado obtenido (extracto real)

- **`tools/list`**: expuso exactamente 2 herramientas operativas: `resolve-library-id` y `query-docs`.
- **`resolve-library-id`**: devolvió como primera coincidencia `/remix-run/react-router` (`Source Reputation: High`, `Benchmark Score: 74.88`, `Versions: ..., v6.3.0, 7.6.2, ...`) y `/websites/reactrouter` (`Versions: 6.30.3, v5, 7.13.0`).
- **`query-docs`** sobre `/remix-run/react-router`:
  ```tsx
  function SearchResults() {
    let [searchParams] = useSearchParams();
    return (
      <div>
        <p>
          You searched for <i>{searchParams.get("q")}</i>
        </p>
        <FakeSearchResults />
      </div>
    );
  }
  ```
  Firma verificada:
  ```tsx
  function useSearchParams(
    defaultInit?: URLSearchParamsInit,
  ): [URLSearchParams, SetURLSearchParams]
  ```
  *(El ejemplo devuelto por el snippet general de v7 mostró `import { useSearchParams } from "react-router";`; al contrastar con `frontend/package.json`, el repo fija `"react-router-dom": "6.28.0"`, por lo que en `C-10` corresponde importar desde `"react-router-dom"`).*

## 3. Aporte concreto al change `C-10`

- Confirmó el contrato tipado `[URLSearchParams, SetURLSearchParams]` de `useSearchParams` para leer de forma segura en TypeScript estricto (`P1`, sin `any`):
  - `?token=` en `/checkout-simulado` (`checkout_token` de 1 uso) y en `/mail/confirmar` / `/mail/cancelar`.
  - `?dni=&token=` en `/mis-turnos` (evitando exponer consultas solo por DNI, regla `P12`).
- Permitió documentar en `design.md` el límite real del MCP al consultar documentación general de un repositorio multi-versión y la necesidad de validar imports contra `frontend/package.json`.
