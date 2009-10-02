/*!
  \file vector/Vlib/ascii.c
 
  \brief Vector library - GRASS ASCII vector format
 
  Higher level functions for reading/writing/manipulating vectors.
  
  (C) 2001-2009 by the GRASS Development Team
  
  This program is free software under the GNU General Public License
  (>=v2).  Read the file COPYING that comes with GRASS for details.
  
  \author Original author CERL
*/
#include <stdio.h>

#include <grass/vector.h>
#include <grass/dbmi.h>
#include <grass/glocale.h>

#define BUFFSIZE 128

static int srch(const void *, const void *);

/*!
  \brief Read data in GRASS ASCII vector format

  \param ascii pointer to the ASCII file
  \param Map   pointer to Map_info structure

  \return number of read features
  \return -1 on error
*/
int Vect_read_ascii(FILE *ascii, struct Map_info *Map)
{
    char ctype;
    char buff[BUFFSIZE];
    double *xarray;
    double *yarray;
    double *zarray;
    double *x, *y, *z;
    int i, n_points, n_coors, n_cats, n_lines;
    int type;
    int alloc_points;
    int end_of_file;
    struct line_pnts *Points;
    struct line_cats *Cats;
    int catn, cat;

    /* Must always use this to create an initialized  line_pnts structure */
    Points = Vect_new_line_struct();
    Cats = Vect_new_cats_struct();

    end_of_file = 0;
    /*alloc_points     = 1000 ; */
    alloc_points = 1;
    xarray = (double *)G_calloc(alloc_points, sizeof(double));
    yarray = (double *)G_calloc(alloc_points, sizeof(double));
    zarray = (double *)G_calloc(alloc_points, sizeof(double));

    n_lines = 0;
    while (G_getl2(buff, BUFFSIZE - 1, ascii) != 0) {
	n_cats = 0;
	if (buff[0] == '\0') {
	    G_debug(3, "a2b: skipping blank line");
	    continue;
	}

	if (sscanf(buff, "%1c%d%d", &ctype, &n_coors, &n_cats) < 2 ||
	    n_coors < 0 || n_cats < 0) {
	    if (ctype == '#') {
		G_debug(2, "a2b: skipping commented line");
		continue;
	    }
	    G_fatal_error(_("Error reading ASCII file: (bad type) [%s]"),
			  buff);
	}
	if (ctype == '#') {
	    G_debug(2, "a2b: Skipping commented line");
	    continue;
	}

	switch (ctype) {
	case 'A':
	    type = GV_BOUNDARY;
	    break;
	case 'B':
	    type = GV_BOUNDARY;
	    break;
	case 'C':
	    type = GV_CENTROID;
	    break;
	case 'L':
	    type = GV_LINE;
	    break;
	case 'P':
	    type = GV_POINT;
	    break;
	case 'F':
	    type = GV_FACE;
	    break;
	case 'K':
	    type = GV_KERNEL;
	    break;
	case 'a':
	case 'b':
	case 'c':
	case 'l':
	case 'p':
	    type = 0;		/* dead -> ignore */
	    break;
	default:
	    G_fatal_error(_("Error reading ASCII file: (unknown type) [%s]"),
			  buff);
	}
	G_debug(5, "feature type = %d", type);

	n_points = 0;
	x = xarray;
	y = yarray;
	z = zarray;

	/* Collect the points */
	for (i = 0; i < n_coors; i++) {
	    if (G_getl2(buff, BUFFSIZE - 1, ascii) == 0)
		G_fatal_error(_("End of ASCII file reached before end of coordinates"));

	    if (buff[0] == '\0') {
		G_debug(3, "a2b: skipping blank line while reading vertices");
		i--;
		continue;
	    }

	    *z = 0;
	    if (sscanf(buff, "%lf%lf%lf", x, y, z) < 2)
		G_fatal_error(_("Error reading ASCII file: (bad point) [%s]"),
			      buff);

	    G_debug(5, "coor in: %s -> x = %f y = %f z = %f", G_chop(buff),
		    *x, *y, *z);

	    n_points++;
	    x++;
	    y++;
	    z++;

	    if (n_points >= alloc_points) {
		alloc_points = n_points + 1000;
		xarray =
		    (double *)G_realloc((void *)xarray,
					alloc_points * sizeof(double));
		yarray =
		    (double *)G_realloc((void *)yarray,
					alloc_points * sizeof(double));
		zarray =
		    (double *)G_realloc((void *)zarray,
					alloc_points * sizeof(double));
		x = xarray + n_points;
		y = yarray + n_points;
		z = zarray + n_points;
	    }
	}

	/* Collect the cats */
	for (i = 0; i < n_cats; i++) {
	    if (G_getl2(buff, BUFFSIZE - 1, ascii) == 0)
		G_fatal_error(_("End of ASCII file reached before end of categories"));

	    if (buff[0] == '\0') {
		G_debug(3,
			"a2b: skipping blank line while reading category info");
		i--;
		continue;
	    }

	    if (sscanf(buff, "%u%u", &catn, &cat) != 2)
		G_fatal_error(_("Error reading categories: [%s]"), buff);

	    Vect_cat_set(Cats, catn, cat);
	}

	/* Allocation is handled for line_pnts */
	if (0 >
	    Vect_copy_xyz_to_pnts(Points, xarray, yarray, zarray, n_points))
	    G_fatal_error(_("Out of memory"));

	if (type > 0) {
	    Vect_write_line(Map, type, Points, Cats);
	    n_lines++;
	}
	
	Vect_reset_cats(Cats);
    }
    return n_lines;
}

/*!
  \brief Read header of GRASS ASCII vector format

  \param dascii pointer to the ASCII file
  \param Map    pointer to Map_info structure

  \return 0 on success
  \return -1 on error
*/
int Vect_read_ascii_head(FILE *dascii, struct Map_info *Map)
{
    char buff[1024];
    char *ptr;

    for (;;) {
	if (0 == G_getl2(buff, sizeof(buff) - 1, dascii))
	    return (0);

	/* Last line of header */
	if (strncmp(buff, "VERTI:", 6) == 0)
	    return (0);

	if (!(ptr = G_index(buff, ':')))
	    G_fatal_error(_("Unexpected data in vector head:\n[%s]"), buff);

	ptr++;			/* Search for the start of text */
	while (*ptr == ' ')
	    ptr++;

	if (strncmp(buff, "ORGANIZATION:", 12) == 0)
	    Vect_set_organization(Map, ptr);
	else if (strncmp(buff, "DIGIT DATE:", 11) == 0)
	    Vect_set_date(Map, ptr);
	else if (strncmp(buff, "DIGIT NAME:", 11) == 0)
	    Vect_set_person(Map, ptr);
	else if (strncmp(buff, "MAP NAME:", 9) == 0)
	    Vect_set_map_name(Map, ptr);
	else if (strncmp(buff, "MAP DATE:", 9) == 0)
	    Vect_set_map_date(Map, ptr);
	else if (strncmp(buff, "MAP SCALE:", 10) == 0)
	    Vect_set_scale(Map, atoi(ptr));
	else if (strncmp(buff, "OTHER INFO:", 11) == 0)
	    Vect_set_comment(Map, ptr);
	else if (strncmp(buff, "ZONE:", 5) == 0 ||
		 strncmp(buff, "UTM ZONE:", 9) == 0)
	    Vect_set_zone(Map, atoi(ptr));
	else if (strncmp(buff, "WEST EDGE:", 10) == 0) {
	}
	else if (strncmp(buff, "EAST EDGE:", 10) == 0) {
	}
	else if (strncmp(buff, "SOUTH EDGE:", 11) == 0) {
	}
	else if (strncmp(buff, "NORTH EDGE:", 11) == 0) {
	}
	else if (strncmp(buff, "MAP THRESH:", 11) == 0)
	    Vect_set_thresh(Map, atof(ptr));
	else {
	    G_warning(_("Unknown keyword <%s> in vector head"), buff);
	}
    }
    /* NOTREACHED */
}

/*!
  \brief Write data to GRASS ASCII vector format

  \param dascii pointer to the ASCII file
  \param Map    pointer to Map_info structure

  \return 0 on sucess
  \return -1 on error
*/
int Vect_write_ascii(FILE *ascii,
		     FILE *att, struct Map_info *Map, int ver,
		     int format, int dp, char *fs, int region_flag,
		     int field, char* where, char **columns)
{
    int type, ctype, i, cat, proj;
    double *xptr, *yptr, *zptr, x, y;
    static struct line_pnts *Points;
    struct line_cats *Cats;
    char *xstring = NULL, *ystring = NULL, *zstring = NULL;
    struct Cell_head window;
    struct ilist *fcats;

    /* where */
    struct field_info *Fi;
    dbDriver *driver;
    dbValue value = {0};
    dbHandle handle;
    int *cats, ncats;
    
    /* get the region */
    G_get_window(&window);

    ncats = 0;
    cats = NULL;
    
    if (where || columns) {
	Fi = Vect_get_field(Map, field);
	if (!Fi) {
	    G_fatal_error(_("Database connection not defined for layer %d"),
			  field);
	}

	driver = db_start_driver(Fi->driver);
	if (!driver)
	    G_fatal_error(_("Unable to start driver <%s>"), Fi->driver);
	
	db_init_handle(&handle);
	db_set_handle(&handle, Fi->database, NULL);
	
	if (db_open_database(driver, &handle) != DB_OK)
	    G_fatal_error(_("Unable to open database <%s> by driver <%s>"),
			  Fi->database, Fi->driver);
	
	/* select cats (sorted array) */
	ncats = db_select_int(driver, Fi->table, Fi->key, where, &cats);
	G_debug(3, "%d categories selected from table <%s>", ncats, Fi->table);

	if (!columns) {
	    db_close_database(driver);
	    db_shutdown_driver(driver);
	}
    }
    
    Points = Vect_new_line_struct();	/* init line_pnts struct */
    Cats = Vect_new_cats_struct();
    fcats = Vect_new_list();

    proj = Vect_get_proj(Map);

    /* by default, read_next_line will NOT read Dead lines */
    /* but we can override that (in Level I only) by specifying */
    /* the type  -1, which means match all line types */

    Vect_rewind(Map);

    while (1) {
	if (-1 == (type = Vect_read_next_line(Map, Points, Cats))) {
	    if (columns) {
		db_close_database(driver);
		db_shutdown_driver(driver);
	    }
	    
	    return -1;
	}

	if (type == -2)	{	/* EOF */
	    if (columns) {
		db_close_database(driver);
		db_shutdown_driver(driver);
	    }
	    return 0;
	}

	if (format == GV_ASCII_FORMAT_POINT && !(type & GV_POINTS))
	    continue;

	if (cats) {
	    /* check category */
	    for (i = 0; i < Cats->n_cats; i++) {
		if ((int *)bsearch((void *) &(Cats->cat[i]), cats, ncats, sizeof(int),
				   srch)) {
		    /* found */
		    break;
		}
	    }
	    
	    if (i == Cats->n_cats) 
		continue;
	}

	if (ver < 5) {
	    Vect_cat_get(Cats, 1, &cat);
	}

	switch (type) {
	case GV_BOUNDARY:
	    if (ver == 5)
		ctype = 'B';
	    else
		ctype = 'A';
	    break;
	case GV_CENTROID:
	    if (ver < 5) {
		if (att != NULL) {
		    if (cat > 0) {
			G_asprintf(&xstring, "%.*f", dp, Points->x[0]);
			G_trim_decimal(xstring);
			G_asprintf(&ystring, "%.*f", dp, Points->y[0]);
			G_trim_decimal(ystring);
			fprintf(att, "A %s %s %d\n", xstring, ystring, cat);
		    }
		}
		continue;
	    }
	    ctype = 'C';
	    break;
	case GV_LINE:
	    ctype = 'L';
	    break;
	case GV_POINT:
	    ctype = 'P';
	    break;
	case GV_FACE:
	    ctype = 'F';
	    break;
	case GV_KERNEL:
	    ctype = 'K';
	    break;
	default:
	    ctype = 'X';
	    G_warning(_("got type %d"), (int)type);
	    break;
	}

	if (format == GV_ASCII_FORMAT_POINT) {
	    /*fprintf(ascii, "%c", ctype); */

	    if (region_flag) {
		if ((window.east < Points->x[0]) ||
		    (window.west > Points->x[0]))
		    continue;
	    }
	    G_asprintf(&xstring, "%.*f", dp, Points->x[0]);
	    G_trim_decimal(xstring);

	    if (region_flag) {
		if ((window.north < Points->y[0]) ||
		    (window.south > Points->y[0]))
		    continue;
	    }
	    G_asprintf(&ystring, "%.*f", dp, Points->y[0]);
	    G_trim_decimal(ystring);

	    if (Map->head.with_z && ver == 5) {
		if (region_flag) {
		    if ((window.top < Points->z[0]) ||
			(window.bottom > Points->z[0]))
			continue;
		}
		G_asprintf(&zstring, "%.*f", dp, Points->z[0]);
		G_trim_decimal(zstring);
		fprintf(ascii, "%s%s%s%s%s", xstring, fs, ystring, fs,
			zstring);
	    }
	    else {
		fprintf(ascii, "%s%s%s", xstring, fs, ystring);
	    }

	    Vect_field_cat_get(Cats, field, fcats);
	    
	    if (fcats->n_values > 0) {
		if (fcats->n_values > 1) {
		    G_warning(_("Feature has more categories. Only first category (%d) "
				"is exported."), fcats->value[0]);
		}
		fprintf(ascii, "%s%d", fs, fcats->value[0]);
		
		/* print attributes */
		if (columns) {
		    for(i = 0; columns[i]; i++) {
			if (db_select_value(driver, Fi->table, Fi->key, fcats->value[0],
					    columns[i], &value) < 0)
			    G_fatal_error(_("Unable to select record from table <%s> (key %s, column %s)"),
					  Fi->table, Fi->key, columns[i]);
			
			if (db_test_value_isnull(&value)) {
			    fprintf(ascii, "%s", fs);
			}
			else {
			    switch(db_column_Ctype(driver, Fi->table, columns[i]))
			    {
			    case DB_C_TYPE_INT: {
				fprintf(ascii, "%s%d", fs, db_get_value_int(&value));
				break;
			    }
			    case DB_C_TYPE_DOUBLE: {
				fprintf(ascii, "%s%.*f", fs, dp, db_get_value_double(&value));
				break;
			    }
			    case DB_C_TYPE_STRING: {
				fprintf(ascii, "%s%s", fs, db_get_value_string(&value));
				break;
			    }
			    case DB_C_TYPE_DATETIME: {
				break;
			    }
			    case -1:
				G_fatal_error(_("Column <%s> not found in table <%s>"),
					      columns[i], Fi->table);
			    default: G_fatal_error(_("Column <%s>: unsupported data type"),
						   columns[i]);
			    }
			}
		    }
		}
	    }

	    fprintf(ascii, "\n");
	}
	else {
	    /* FORMAT_STANDARD */
	    if (ver == 5 && Cats->n_cats > 0)
		fprintf(ascii, "%c  %d %d\n", ctype, Points->n_points,
			Cats->n_cats);
	    else
		fprintf(ascii, "%c  %d\n", ctype, Points->n_points);

	    xptr = Points->x;
	    yptr = Points->y;
	    zptr = Points->z;

	    while (Points->n_points--) {

		G_asprintf(&xstring, "%.*f", dp, *xptr++);
		G_trim_decimal(xstring);
		G_asprintf(&ystring, "%.*f", dp, *yptr++);
		G_trim_decimal(ystring);

		if (ver == 5) {
		    if (Map->head.with_z) {
			G_asprintf(&zstring, "%.*f", dp, *zptr++);
			G_trim_decimal(zstring);
			fprintf(ascii, " %-12s %-12s %-12s\n", xstring,
				ystring, zstring);
		    }
		    else {
			fprintf(ascii, " %-12s %-12s\n", xstring, ystring);
		    }
		}		/*Version 4 */
		else {
		    fprintf(ascii, " %-12s %-12s\n", ystring, xstring);
		}
	    }

	    if (ver == 5) {
		for (i = 0; i < Cats->n_cats; i++) {
		    fprintf(ascii, " %-5d %-10d\n", Cats->field[i],
			    Cats->cat[i]);
		}
	    }
	    else {
		if (cat > 0) {
		    if (type == GV_POINT) {
			G_asprintf(&xstring, "%.*f", dp, Points->x[0]);
			G_trim_decimal(xstring);
			G_asprintf(&ystring, "%.*f", dp, Points->y[0]);
			G_trim_decimal(ystring);
			fprintf(att, "P %s %s %d\n", xstring, ystring, cat);
		    }
		    else {
			x = (Points->x[1] + Points->x[0]) / 2;
			y = (Points->y[1] + Points->y[0]) / 2;

			G_asprintf(&xstring, "%.*f", dp, x);
			G_trim_decimal(xstring);
			G_asprintf(&ystring, "%.*f", dp, y);
			G_trim_decimal(ystring);
			fprintf(att, "L %s %s %d\n", xstring, ystring, cat);
		    }
		}
	    }
	}
    }

    /* not reached */
}

int srch(const void *pa, const void *pb)
{
    int *p1 = (int *)pa;
    int *p2 = (int *)pb;
    
    if (*p1 < *p2)
	return -1;
    if (*p1 > *p2)
	return 1;
    return 0;
}

/*!
  \brief Write data to GRASS ASCII vector format

  \param dascii pointer to the ASCII file
  \param Map    pointer to Map_info structure
*/
void Vect_write_ascii_head(FILE *dascii, struct Map_info *Map)
{
    fprintf(dascii, "ORGANIZATION: %s\n", Vect_get_organization(Map));
    fprintf(dascii, "DIGIT DATE:   %s\n", Vect_get_date(Map));
    fprintf(dascii, "DIGIT NAME:   %s\n", Vect_get_person(Map));
    fprintf(dascii, "MAP NAME:     %s\n", Vect_get_map_name(Map));
    fprintf(dascii, "MAP DATE:     %s\n", Vect_get_map_date(Map));
    fprintf(dascii, "MAP SCALE:    %d\n", Vect_get_scale(Map));
    fprintf(dascii, "OTHER INFO:   %s\n", Vect_get_comment(Map));
    fprintf(dascii, "ZONE:         %d\n", Vect_get_zone(Map));
    fprintf(dascii, "MAP THRESH:   %f\n", Vect_get_thresh(Map));
}
