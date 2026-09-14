// ============================================================
// ADMIN - ANDAMIAJE DEL PANEL (Etapa 2)
// ============================================================
// Se carga DESPUÉS de templates.js (que declara `const TEMPLATES`): agrega la
// clave 'admin'. Cada vista llena su propio -body desde su archivo.

TEMPLATES['admin'] = `
  <div id="admin-chip" class="admin-chip admin-chip-gris">Estado del almacén: consultando…</div>
  <div id="admin-banner" class="admin-banner" style="display:none"></div>

  <div class="section" id="admin-usuarios">
    <h3 class="admin-titulo">👤 Usuarios</h3>
    <div id="admin-usuarios-body" class="admin-body"></div>
  </div>

  <div class="section" id="admin-roles">
    <h3 class="admin-titulo">🔑 Roles y permisos</h3>
    <div id="admin-roles-body" class="admin-body"></div>
  </div>

  <div class="section" id="admin-estado">
    <h3 class="admin-titulo">🗄️ Estado del almacén</h3>
    <div id="admin-estado-body" class="admin-body"></div>
  </div>

  <div class="section" id="admin-auditoria">
    <h3 class="admin-titulo">🧾 Auditoría</h3>
    <div id="admin-auditoria-body" class="admin-body"></div>
  </div>

  <div class="section" id="admin-accesos">
    <h3 class="admin-titulo">🚫 Accesos rechazados</h3>
    <div id="admin-accesos-body" class="admin-body"></div>
  </div>
`;

console.log('✅ admin/template.js cargado');
