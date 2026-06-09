shader_type canvas_item;
render_mode unshaded, skip_vertex_transform;

uniform float curvature = 9.0;
uniform sampler2D screen_texture : hint_screen_texture;
uniform float mask_size : hint_range(0.0, 10.0) = 1.0;
uniform float color_boost: hint_range(0.0, 10.0) = 1.0;
uniform float chromatic_abberation : hint_range(0.0, 10.0) = 1.0;

vec3 generate_mask(vec2 fragcoord){
	const vec3 pattern[16] = {
		vec3(1,0,1), vec3(0,1,0), vec3(1,0,1), vec3(0,1,0),
		vec3(0,0,1), vec3(0,1,0), vec3(1,0,0), vec3(0,0,0),
		vec3(1,0,1), vec3(0,1,0), vec3(1,0,1), vec3(0,1,0),
		vec3(1,0,0), vec3(0,0,0), vec3(0,0,1), vec3(0,1,0)
		};
	ivec2 icoords = ivec2(fragcoord/mask_size)%4;
	return pattern[icoords.y * 4 + icoords.x];
}

void fragment() {
	// Called for every pixel the material is visible on.
	vec2 centered_uv = SCREEN_UV * 2.0 -1.0;// this is the centered uv

	vec2 uv_offset = centered_uv.yx / curvature;// to find the uv_offset you ahve to divied y,x by a set amount

	vec2 warped_uv = centered_uv + centered_uv * uv_offset * uv_offset;//for the warping

	vec2 sample_uv = (warped_uv + 1.0)/2.0;

	vec2 dist = sample_uv - 0.5;

	float r = texture(screen_texture, sample_uv + (dist * chromatic_abberation)).r;
	float g = texture(screen_texture, sample_uv).g;
	float b = texture(screen_texture, sample_uv - (dist * chromatic_abberation)).b;

	vec3 cutoff = vec3(step(abs(warped_uv.x), 1.0) * step(abs(warped_uv.y),1.0));//cutoff
	vec3 screen_color = vec3(r,g,b) * cutoff;
	vec2 mask_coords = FRAGCOORD.xy;
	vec3 mask = generate_mask(mask_coords);
	vec3 mask_color= screen_color * mask * color_boost;
	vec3 color = mix(screen_color * 0.1,mask_color, 1.0);

	vec3 scanlins = vec3(cos (2.0 * warped_uv.y * 90.0)*0.15 + 0.7);

	COLOR = vec4( screen_color * color * scanlins,1.0);
}

