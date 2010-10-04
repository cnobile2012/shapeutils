#
# Development by Carl J. Nobile
#
# $Author$
# $Date$
# $Revision$
#

PREFIX		= $(shell pwd)
PACKAGE_DIR	= $(shell echo $${PWD\#\#*/})
SU_DIR		= $(PREFIX)/shputils
DOCS_DIR	= $(PREFIX)/docs

#----------------------------------------------------------------------
all	: doc tar

#----------------------------------------------------------------------
doc	:
	@(cd $(DOCS_DIR); make)
#----------------------------------------------------------------------
tar	: clean
	@(cd ..; tar -czvf $(PACKAGE_DIR).tar.gz --exclude=".svn" \
          $(PACKAGE_DIR))
#----------------------------------------------------------------------
clean	:
	$(shell $(PREFIX)/cleanDirs.sh clean)
	@(cd ${SU_DIR}; rm -f *~ *.pyc)
	@(cd ${DOCS_DIR}; make clean)

clobber	: clean
	@(cd $(DOCS_DIR); make clobber)
	@rm -f $(LOGS_DIR)/*.log*
