// Brillo de metal al rojo vivo en la boca del cañón.
// "calor" va de 0 (frío, invisible) a 1 (al rojo). Se usa al cuadrado para que el brillo
// aparezca tarde y suba rápido, como el metal de verdad (rojo oscuro -> naranja).
// El borde (efecto fresnel) brilla más: así se ve como un halo, no como pintura plana.
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, shadows_disabled;

uniform float calor : hint_range(0.0, 1.0) = 0.0;

void fragment() {
	float borde = pow(1.0 - abs(dot(NORMAL, VIEW)), 1.5);
	float pulso = 0.88 + 0.12 * sin(TIME * 6.0);
	vec3 rojo = vec3(0.55, 0.04, 0.0);
	vec3 naranja = vec3(1.0, 0.42, 0.06);
	vec3 c = mix(rojo, naranja, smoothstep(0.4, 1.0, calor));
	ALBEDO = c * calor * calor * (0.12 + borde * 1.3) * pulso * 1.2;
}
