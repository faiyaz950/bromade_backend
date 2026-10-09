// Show only the fields that matter for the current choices on the push form.
document.addEventListener('DOMContentLoaded', function () {
  var audience = document.getElementById('id_audience');
  var target = document.getElementById('id_target');
  var screen = document.getElementById('id_screen');
  if (!audience || !target || !screen) return;

  function row(name) {
    return document.querySelector('.form-row.field-' + name);
  }

  function show(name, visible) {
    var el = row(name);
    if (el) el.style.display = visible ? '' : 'none';
  }

  function update() {
    var partners = audience.value === 'partners';
    show('city', target.value === 'city');
    show('recipient', target.value === 'person');
    show('screen', !partners);
    show('service', !partners && screen.value === 'service');
    show('package', !partners && screen.value === 'package');
  }

  [audience, target, screen].forEach(function (el) {
    el.addEventListener('change', update);
  });
  update();
});
