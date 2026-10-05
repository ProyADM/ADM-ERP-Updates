// ============================================================
// ADMIN - ANDAMIAJE DEL PANEL (Etapa 2)
// ============================================================
// Se carga DESPUÉS de templates.js (que declara `const TEMPLATES`): agrega la
// clave 'admin'. Cada vista llena su propio -body desde su archivo.

TEMPLATES['admin'] = `
  <div id="admin-chip" class="admin-chip admin-chip-gris" data-tooltip="adminChipEstado">Estado del almacén: consultando…</div>
  <div id="admin-banner" class="admin-banner" style="display:none"></div>

  <div class="section" id="admin-usuarios">
    <h3 class="admin-titulo" data-tooltip="drawerAdminUsuarios">👤 Usuarios</h3>
    <div id="admin-usuarios-body" class="admin-body"></div>
  </div>

  <div class="section" id="admin-roles">
    <h3 class="admin-titulo" data-tooltip="drawerAdminRoles">🔑 Roles y permisos</h3>
    <div id="admin-roles-body" class="admin-body"></div>
  </div>

  <div class="section" id="admin-estado">
    <h3 class="admin-titulo" data-tooltip="drawerAdminEstado">🗄️ Estado del almacén</h3>
    <div id="admin-estado-body" class="admin-body"></div>
  </div>

  <div class="section" id="admin-auditoria">
    <h3 class="admin-titulo" data-tooltip="drawerAdminAuditoria">🧾 Auditoría</h3>
    <div id="admin-auditoria-body" class="admin-body"></div>
  </div>

  <div class="section" id="admin-accesos">
    <h3 class="admin-titulo" data-tooltip="drawerAdminAccesos">🚫 Accesos rechazados</h3>
    <div id="admin-accesos-body" class="admin-body"></div>
  </div>

  <div class="section" id="admin-diagnostico">
    <h3 class="admin-titulo" data-tooltip="drawerAdminDiagnostico">🩺 Diagnóstico</h3>
    <div id="admin-diagnostico-body" class="admin-body"></div>
  </div>
`;

console.log('✅ admin/template.js cargado');
