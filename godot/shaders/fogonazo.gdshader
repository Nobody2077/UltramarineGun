// Fogonazo del bólter.
// - blend_add: el color se SUMA a lo que hay detrás (el fuego ilumina, nunca oscurece).
// - unshaded: no le afectan las luces, brilla por sí solo.
// - La forma viene de una textura (estrella o llama) y se deforma con ruido distinto
//   en cada disparo (la "semilla"), así ningún fogonazo es igual al anterior.
shader_type spatial;
render_mode unshaded, blend_add, cull_disabled, depth_draw_never, shadows_disabled;

uniform sampler2D forma : source_color, filter_linear, repeat_disable;
uniform vec3 color_nucleo : source_color = vec3(1.0, 0.93, 0.75);
uniform vec3 color_borde : source_color = vec3(1.0, 0.32, 0.04);
uniform float intensidad = 3.0;
uniform float semilla = 0.0;

float azar(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float ruido(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(azar(i), azar(i + vec2(1.0, 0.0)), u.x),
	           mix(azar(i + vec2(0.0, 1.0)), azar(i + vec2(1.0, 1.0)), u.x), u.y);
}

void fragment() {
	vec2 s = vec2(semilla * 13.17, semilla * 7.31);
	float n = ruido(UV * 7.0 + s);
	float n2 = ruido(UV * 19.0 - s);
	vec2 uv = UV + (vec2(n, n2) - 0.5) * 0.08;
	vec4 t = texture(forma, uv);
	float a = t.a * (0.6 + 0.7 * n) * (0.8 + 0.4 * n2);
	// el canal verde de la textura es alto en el núcleo (blanco) y bajo en el borde (naranja)
	float nucleo = smoothstep(0.55, 1.0, t.g);
	vec3 c = mix(color_borde, color_nucleo, nucleo);
	ALBEDO = c * intensidad * a;
}
