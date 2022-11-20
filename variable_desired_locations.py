import glyphsLib
import fontTools
from fontTools.ttLib import TTFont, newTable


def get_instance_locations(gsfont):
    axes_tags = {_.name: _.axisTag for _ in gsfont.axes}
    instance_locations = {}
    for instance in gsfont.instances:
        instance_locations[instance.name] = {
            axes_tags[_["Axis"]]: float(_["Location"])
            for _ in instance.customParameters["Axis Location"]
        }

    return instance_locations


def get_current_instance_locations(ttfont):
    name = ttfont["name"]
    instances = {
        name.getName(_.subfamilyNameID, 3, 1).toUnicode(): _.coordinates
        for _ in ttfont["fvar"].instances
    }
    return instances


def get_gvar_instance_locations(gsfont):
    axes_tags = [_.axisTag for _ in gsfont.axes]
    instance_locations = {}
    for instance in gsfont.instances:
        instance_locations[instance.name] = {
            axis_tag: 0.0 for axis_tag in axes_tags
        }
        for i, axis_value in enumerate(instance.axes[:len(axes_tags)]):
            instance_locations[instance.name][axes_tags[i]] = axis_value

    return instance_locations


def get_axes_values(ttfont):
    axes_values = {
        _.axisTag: {
            "max": _.maxValue,
            "min": _.minValue,
            "def": _.defaultValue,
        }
        for _ in ttfont["fvar"].axes
    }
    return axes_values


def get_source_axes_values(gsfont):
    axes_tags = [_.axisTag for _ in gsfont.axes]
    default_master = [
        m
        for m in gsfont.masters
        if m.id == gsfont.customParameters["Variable Font Origin"]
    ][0]

    axes_values = {}
    for axis_index, axis_tag in enumerate(axes_tags):
        default_value = 0.0
        try:
            default_value = default_master.axes[axis_index]
        except IndexError:
            pass

        max_value = -float("Inf")
        min_value = float("Inf")
        for master in gsfont.masters:
            value = 0.0
            try:
                value = master.axes[axis_index]
            except IndexError:
                pass
            if value > max_value:
                max_value = value
            if value < min_value:
                min_value = value

        axes_values[axis_tag] = {
            "def": default_value,
            "min": min_value,
            "max": max_value,
        }
    return axes_values


def defaultNormalizedValue(axis, instanceValue):
    if instanceValue < axis["def"]:
        return -float(axis["def"] - instanceValue) / (axis["def"] - axis["min"])
    elif instanceValue > axis["def"]:
        return float(instanceValue - axis["def"]) / (axis["max"] - axis["def"])
    else:
        return 0.0


def create_avar(ttfont, gsfont, verbose=True):
    avar = newTable("avar")

    axes_values = get_axes_values(ttfont)
    source_axes_values = get_source_axes_values(gsfont)
    current_locations = get_gvar_instance_locations(gsfont)
    desired_locations = get_instance_locations(gsfont)

    max_name_len = max(len(_.name) for _ in gsfont.instances)

    for axis_tag, axis_values in axes_values.items():
        curve = avar.segments[axis_tag] = {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0}
        for instance_name, current_location in current_locations.items():
            if verbose:
                print(
                    f"{axis_tag:4s} | {instance_name + ' ' * (max_name_len - len(instance_name))} : {current_location[axis_tag]:3.1f} => {desired_locations[instance_name][axis_tag]:3.1f}"
                )
            curve[
                float(
                    defaultNormalizedValue(
                        axis_values, desired_locations[instance_name][axis_tag]
                    )
                )
            ] = defaultNormalizedValue(
                source_axes_values[axis_tag], current_location[axis_tag]
            )
    ttfont["avar"] = avar


def get_name(ttfont, id):
    return ttfont["name"].getName(id, 3, 1).toUnicode()


def update_stat(ttfont, gsfont):
    desired_locations = get_instance_locations(gsfont)
    stat = ttfont["STAT"].table
    fvar = ttfont["fvar"]
    axes_tags = [_.AxisTag for _ in stat.DesignAxisRecord.Axis]
    stat.AxisValueArray.AxisValue = []
    for instance in fvar.instances:
        instance_name = get_name(ttfont, instance.subfamilyNameID)
        for axisIndex, axis in enumerate(stat.DesignAxisRecord.Axis):
            axis_tag = axes_tags[axisIndex]
            if axis_tag not in desired_locations[instance_name]:
                continue
            axis_value = fontTools.ttLib.tables.otTables.AxisValue()
            axis_value.Format = 1
            axis_value.AxisIndex = axisIndex
            axis_value.Flags = 0
            axis_value.ValueNameID = instance.subfamilyNameID
            axis_value.Value = desired_locations[instance_name][axis_tag]
            stat.AxisValueArray.AxisValue.append(axis_value)


def update_fvar(ttfont, gsfont):
    desired_locations = get_instance_locations(gsfont)
    fvar = ttfont["fvar"]

    for instance in fvar.instances:
        instance_name = get_name(ttfont, instance.subfamilyNameID)
        for axis_tag in instance.coordinates:
            instance.coordinates[axis_tag] = desired_locations[instance_name][
                axis_tag
            ]


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="""
        Change generated TTFont instance axes values to desired from GSFont.
        Each variable instance of the GSFont must contains AxisLocation custom parameter with desired values.
    """
    )
    parser.add_argument("ttfont", type=str, help="TTF varible font path.")
    parser.add_argument("gsfont", type=str, help="GS font source path.")

    args = parser.parse_args()

    ttfont = TTFont(args.ttfont)
    gsfont = glyphsLib.GSFont(args.gsfont)

    create_avar(ttfont, gsfont)
    update_stat(ttfont, gsfont)
    update_fvar(ttfont, gsfont)

    save_path = ".".join(args.ttfont.split(".")[:-1]) + "_avar.ttf"
    print(f"Saved as: {save_path}")
    ttfont.save(save_path)


if __name__ == "__main__":
    main()
