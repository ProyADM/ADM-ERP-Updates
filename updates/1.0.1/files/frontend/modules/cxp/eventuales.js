// ============================================================
// EVENTUALES - PROVEEDORES EVENTUALES
// ============================================================

export function aplicarEventualGlobal() {
    const checked = document.getElementById('toggleEventualGlobal')?.checked || false;
    const panel = document.getElementById('eventualGlobalPanel');
    if (panel) panel.style.display = checked ? 'block' : 'none';
    for (let i = 0; i < window.facturasData?.length; i++) {
        const chk = document.getElementById(`f${i}_esev`);
        if (chk) { chk.checked = checked; toggleEventualFact(i); }
    }
}

export function toggleEventualFact(i) {
    const checked = document.getElementById(`f${i}_esev`)?.checked || false;
    const provWrap = document.getElementById(`f${i}_provwrap`);
    const evPanel = document.getElementById(`f${i}_evpanel`);
    if (provWrap) provWrap.style.display = checked ? 'flex' : 'none';
    if (evPanel) evPanel.style.display = checked ? 'block' : 'none';
    
    const globalId = document.getElementById('empId')?.value;
    const globalText = document.getElementById('empSearch')?.value;
    if (checked && globalText) {
        const provId = document.getElementById(`f${i}_provid`);
        const provSearch = document.getElementById(`f${i}_provsearch`);
        if (globalId && provId) provId.value = globalId;
        if (provSearch) provSearch.value = globalText;
    }
}