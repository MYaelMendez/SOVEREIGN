// Historical conversational specimen supplied by Yæl.
// NOT imported by the corrected simulation or execution kernel.
// Retained solely to document the timer-derived-realization defect.
function authorizeGate(){
  if(pending||realized) return;
  pending=true; buildLedger();
  addWit('🧿 AUTHORIZING...','auth');

  setTimeout(()=>{
    pending=false;
    realized=true;          // canonical violation: time is not evidence
    buildLedger();

    const s=STEPS[si];
    const isState=s.domain==='LEGAL'||s.domain==='PROVENANCE';
    addWit(`🧾 ${s.real}`, isState?'st':'op');
    updateTuple();
  },650);
}
